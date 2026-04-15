"""Fetch advanced stats for the player stat line on the profile page.

Sources:
  1. Baseball Savant — statcast_batter_expected_stats / statcast_pitcher_expected_stats
     Returns xwOBA (est_woba) keyed by MLBAM player_id. Always reliable.

  2. Fangraphs JSON API — direct endpoint (not pybaseball scraper).
     Returns WRC+, WAR for batters and xFIP-, SIERA for pitchers.
     Keyed by xMLBAMID (= MLBAM player_id, no name matching needed).
     Rate-limited: 403 responses are logged and skipped gracefully.

All data is upserted into player_fangraphs_stats.

Usage:
    python -m src.etl.fetch_fangraphs_stats          # current year
    python -m src.etl.fetch_fangraphs_stats --year 2025
"""

import argparse
import logging
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv
from pybaseball import statcast_batter_expected_stats, statcast_pitcher_expected_stats
from supabase import create_client

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

FG_BASE = "https://www.fangraphs.com/api/leaders/major-league/data"
FG_HEADERS = {"User-Agent": "Mozilla/5.0"}
FG_TIMEOUT = 20


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _fetch_statcast_xwoba(season: int) -> dict[int, float]:
    """Returns {mlbam_id: xwoba} for batters and pitchers combined."""
    result: dict[int, float] = {}
    try:
        batter_df = statcast_batter_expected_stats(season)
        for _, row in batter_df.iterrows():
            pid = int(row["player_id"])
            xw = row.get("est_woba")
            if pid and xw is not None:
                result[pid] = float(xw)
        logger.info(f"  Statcast batter xwOBA: {len(result)} players")
    except Exception as e:
        logger.warning(f"  Statcast batter expected stats failed: {e}")

    try:
        pitcher_df = statcast_pitcher_expected_stats(season)
        pitcher_count = 0
        for _, row in pitcher_df.iterrows():
            pid = int(row["player_id"])
            xw = row.get("est_woba")
            if pid and xw is not None:
                result[pid] = float(xw)
                pitcher_count += 1
        logger.info(f"  Statcast pitcher xwOBA: {pitcher_count} players")
    except Exception as e:
        logger.warning(f"  Statcast pitcher expected stats failed: {e}")

    return result


def _fetch_fg(stats: str, season: int) -> list[dict]:
    """Fetch Fangraphs leaderboard (stats='bat' or 'pit'). Returns [] on 403."""
    params = {
        "age": "", "pos": "all", "stats": stats, "lg": "all",
        "season": season, "season1": season, "ind": 0, "qual": 0,
        "type": 8, "month": 0, "pageitems": 2000, "pagenum": 1,
    }
    try:
        r = requests.get(FG_BASE, params=params, headers=FG_HEADERS, timeout=FG_TIMEOUT)
        if r.status_code == 403:
            logger.warning(f"  Fangraphs {stats} returned 403 — skipping (will retry next run)")
            return []
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.warning(f"  Fangraphs {stats} fetch failed: {e}")
        return []


def build_rows(season: int) -> dict[int, dict]:
    """Returns {player_id: row_dict} merged from all sources."""
    rows: dict[int, dict] = {}

    def get_row(pid: int) -> dict:
        if pid not in rows:
            rows[pid] = {"player_id": pid, "season_year": season}
        return rows[pid]

    # ── xWOBA from Baseball Savant ────────────────────────────────────────────
    logger.info("Fetching xWOBA from Baseball Savant...")
    xwoba_map = _fetch_statcast_xwoba(season)
    for pid, xw in xwoba_map.items():
        get_row(pid)["xwoba"] = xw

    # ── WRC+, WAR from Fangraphs batting ─────────────────────────────────────
    logger.info("Fetching WRC+/WAR from Fangraphs (batting)...")
    fg_bat = _fetch_fg("bat", season)
    for row in fg_bat:
        pid = row.get("xMLBAMID")
        if not pid:
            continue
        pid = int(pid)
        r = get_row(pid)
        if row.get("wRC+") is not None:
            r["wrc_plus"] = float(row["wRC+"])
        if row.get("WAR") is not None:
            r["war"] = float(row["WAR"])
    logger.info(f"  Fangraphs batting: {len(fg_bat)} records")

    # Sleep to avoid rate-limiting the pitching call
    time.sleep(5)

    # ── xFIP-, SIERA from Fangraphs pitching ─────────────────────────────────
    logger.info("Fetching xFIP-/SIERA from Fangraphs (pitching)...")
    fg_pit = _fetch_fg("pit", season)
    for row in fg_pit:
        pid = row.get("xMLBAMID")
        if not pid:
            continue
        pid = int(pid)
        r = get_row(pid)
        if row.get("xFIP-") is not None:
            r["xfip_minus"] = float(row["xFIP-"])
        if row.get("SIERA") is not None:
            r["siera"] = float(row["SIERA"])
    logger.info(f"  Fangraphs pitching: {len(fg_pit)} records")

    return rows


def upsert_rows(sb, rows: dict[int, dict], batch_size: int = 500) -> int:
    existing_ids_resp = sb.table("players").select("player_id").execute()
    existing_ids = {r["player_id"] for r in existing_ids_resp.data}

    filtered = [r for r in rows.values() if r["player_id"] in existing_ids]
    skipped = len(rows) - len(filtered)
    if skipped:
        logger.info(f"  Skipping {skipped} players not in our players table")

    count = 0
    for i in range(0, len(filtered), batch_size):
        batch = filtered[i : i + batch_size]
        sb.table("player_fangraphs_stats").upsert(
            batch, on_conflict="player_id,season_year"
        ).execute()
        count += len(batch)
    logger.info(f"  Upserted {count} rows into player_fangraphs_stats")
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()

    season = args.year
    logger.info(f"Fetching advanced stats for {season}...")

    rows = build_rows(season)
    logger.info(f"Built {len(rows)} player rows")

    sb = _get_supabase()
    total = upsert_rows(sb, rows)
    logger.info(f"Done. {total} rows upserted.")


if __name__ == "__main__":
    main()
