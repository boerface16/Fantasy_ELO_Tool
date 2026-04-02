"""Preseason projection fetcher — FanGraphs ZiPS, ZiPS DC, STEAMER.

Fetches preseason projections and converts them to per-dimension ELO estimates
for the FiveThirtyEight-style season reset formula:

  new_elo = 0.67 * projection_elo + 0.33 * regressed_final_elo
"""

import json
import logging
from typing import Optional

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_FG_URL = "https://www.fangraphs.com/projections?pos=&stats={stats}&type={proj_type}&team=&lg=&players=0"
_FG_STANDINGS_URL = "https://www.fangraphs.com/depthcharts.aspx?position=Standings"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PROJECTION_SYSTEMS = ["steamer", "zips", "zipsdc"]
DEFAULT_ELO = 1500.0

# FanGraphs short name → MLB team code (used in team_elo table)
_FG_NAME_TO_CODE = {
    "Diamondbacks": "ARI", "Braves": "ATL", "Orioles": "BAL", "Red Sox": "BOS",
    "Cubs": "CHC", "White Sox": "CHW", "Reds": "CIN", "Guardians": "CLE",
    "Rockies": "COL", "Tigers": "DET", "Astros": "HOU", "Royals": "KC",
    "Angels": "LAA", "Dodgers": "LAD", "Marlins": "MIA", "Brewers": "MIL",
    "Twins": "MIN", "Mets": "NYM", "Yankees": "NYY", "Athletics": "OAK",
    "Phillies": "PHI", "Pirates": "PIT", "Padres": "SD", "Giants": "SF",
    "Mariners": "SEA", "Cardinals": "STL", "Rays": "TB", "Rangers": "TEX",
    "Blue Jays": "TOR", "Nationals": "WSN",
}

# ELO scaling: stat percentile → ELO offset.
# A player at the 84th percentile (~+1 SD) gets ~+100 ELO above 1500.
ELO_PER_SD = 100.0


def _scrape_fangraphs(url: str) -> list[dict]:
    """Scrape FanGraphs __NEXT_DATA__ payload."""
    r = requests.get(url, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script:
        raise RuntimeError(f"No __NEXT_DATA__ found at {url}")
    data = json.loads(script.string)
    return data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]


def fetch_player_projections(stats: str = "bat") -> Optional[pd.DataFrame]:
    """Fetch and average ZiPS, ZiPS DC, STEAMER projections.

    Args:
        stats: 'bat' for batters, 'pit' for pitchers.

    Returns:
        DataFrame with consensus projections keyed by xMLBAMID,
        or None if fetching fails.
    """
    frames = []
    for system in PROJECTION_SYSTEMS:
        try:
            url = _FG_URL.format(stats=stats, proj_type=system)
            rows = _scrape_fangraphs(url)
            df = pd.DataFrame(rows)
            if "xMLBAMID" not in df.columns:
                logger.warning(f"{system}/{stats}: no xMLBAMID column, skipping")
                continue
            df["system"] = system
            frames.append(df)
            logger.info(f"Fetched {system} {stats}: {len(df)} players")
        except Exception as e:
            logger.warning(f"Failed to fetch {system} {stats}: {e}")

    if not frames:
        logger.error(f"All projection systems failed for {stats}")
        return None

    combined = pd.concat(frames, ignore_index=True)

    # Average numeric columns across systems per player
    id_col = "xMLBAMID"
    numeric_cols = combined.select_dtypes(include="number").columns.tolist()
    if id_col in numeric_cols:
        numeric_cols.remove(id_col)

    consensus = combined.groupby(id_col)[numeric_cols].mean().reset_index()
    # Carry forward PlayerName from first system that has it
    if "PlayerName" in combined.columns:
        names = combined.drop_duplicates(subset=id_col)[["xMLBAMID", "PlayerName"]]
        consensus = consensus.merge(names, on="xMLBAMID", how="left")

    logger.info(f"Consensus {stats} projections: {len(consensus)} players")
    return consensus


def _percentile_to_elo(series: pd.Series) -> pd.Series:
    """Convert a stat series to ELO using z-score scaling."""
    mean = series.mean()
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(DEFAULT_ELO, index=series.index)
    z_scores = (series - mean) / std
    return DEFAULT_ELO + z_scores * ELO_PER_SD


def projection_to_batter_elo(projections: pd.DataFrame) -> dict[int, np.ndarray]:
    """Convert consensus batter projections to 5D ELO arrays.

    Dimensions: [contact, power, discipline, speed, clutch]
    Mapping:
      - contact: 1 - K%  (higher = better contact)
      - power: ISO
      - discipline: BB%
      - speed: SB per 600 PA
      - clutch: default 1500 (no projection available)
    """
    result = {}
    df = projections.copy()

    # Require minimum projected PA for meaningful projections
    if "PA" in df.columns:
        df = df[df["PA"] >= 50]

    # Calculate input stats
    contact_raw = 1 - df["K%"] if "K%" in df.columns else pd.Series(0.5, index=df.index)
    power_raw = df["ISO"] if "ISO" in df.columns else pd.Series(0.15, index=df.index)
    discipline_raw = df["BB%"] if "BB%" in df.columns else pd.Series(0.08, index=df.index)

    if "SB" in df.columns and "PA" in df.columns:
        speed_raw = df["SB"] / (df["PA"] / 600).clip(lower=0.1)
    else:
        speed_raw = pd.Series(5.0, index=df.index)

    # Convert to ELO scale
    contact_elo = _percentile_to_elo(contact_raw)
    power_elo = _percentile_to_elo(power_raw)
    discipline_elo = _percentile_to_elo(discipline_raw)
    speed_elo = _percentile_to_elo(speed_raw)

    for idx, row in df.iterrows():
        mlbam_id = int(row["xMLBAMID"])
        result[mlbam_id] = np.array([
            contact_elo.loc[idx] if idx in contact_elo.index else DEFAULT_ELO,
            power_elo.loc[idx] if idx in power_elo.index else DEFAULT_ELO,
            discipline_elo.loc[idx] if idx in discipline_elo.index else DEFAULT_ELO,
            speed_elo.loc[idx] if idx in speed_elo.index else DEFAULT_ELO,
            DEFAULT_ELO,  # clutch: no projection
        ])

    logger.info(f"Converted {len(result)} batter projections to 5D ELO")
    return result


def projection_to_pitcher_elo(projections: pd.DataFrame) -> dict[int, np.ndarray]:
    """Convert consensus pitcher projections to 4D ELO arrays.

    Dimensions: [stuff, bip_suppression, command, clutch]
    Mapping:
      - stuff: K/9 or K%
      - bip_suppression: 1 - BABIP (inverted: lower BABIP = better)
      - command: 1 - BB% (inverted: lower BB% = better command)
      - clutch: default 1500
    """
    result = {}
    df = projections.copy()

    if "IP" in df.columns:
        df = df[df["IP"] >= 20]
    elif "TBF" in df.columns:
        df = df[df["TBF"] >= 80]

    stuff_raw = df["K/9"] if "K/9" in df.columns else (
        df["K%"] * 9 * 4.3 if "K%" in df.columns else pd.Series(8.0, index=df.index)
    )
    bip_raw = 1 - df["BABIP"] if "BABIP" in df.columns else pd.Series(0.7, index=df.index)
    command_raw = 1 - df["BB%"] if "BB%" in df.columns else (
        1 - df["BB/9"] / 9 / 4.3 if "BB/9" in df.columns else pd.Series(0.92, index=df.index)
    )

    stuff_elo = _percentile_to_elo(stuff_raw)
    bip_elo = _percentile_to_elo(bip_raw)
    command_elo = _percentile_to_elo(command_raw)

    for idx, row in df.iterrows():
        mlbam_id = int(row["xMLBAMID"])
        result[mlbam_id] = np.array([
            stuff_elo.loc[idx] if idx in stuff_elo.index else DEFAULT_ELO,
            bip_elo.loc[idx] if idx in bip_elo.index else DEFAULT_ELO,
            command_elo.loc[idx] if idx in command_elo.index else DEFAULT_ELO,
            DEFAULT_ELO,  # clutch: no projection
        ])

    logger.info(f"Converted {len(result)} pitcher projections to 4D ELO")
    return result


def fetch_team_projected_wins() -> dict[str, float]:
    """Fetch FanGraphs depth chart projected wins per team.

    Returns:
        Dict mapping team short name → projected total wins (W + rxW).
    """
    try:
        rows = _scrape_fangraphs(_FG_STANDINGS_URL)
        result = {}
        for row in rows:
            name = row.get("shortName", "")
            code = _FG_NAME_TO_CODE.get(name, name)
            actual_w = row.get("W", 0)
            rest_w = row.get("rxW", 0)
            result[code] = actual_w + rest_w
        logger.info(f"Fetched projected wins for {len(result)} teams")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch team projected wins: {e}")
        return {}
