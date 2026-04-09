"""Pitcher stats enricher — MLB Stats API with daily file cache.

Fetches season-level pitching stats (G, IP, SV, HLD, SB) from the MLB Stats API.
Caches results as parquet files in .cache/ to avoid repeated API calls.

Batter stats are no longer fetched (they were unused in projections).
"""

import glob
import logging
import os
from datetime import date

import pandas as pd
import requests

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache")

MLB_PITCHING_URL = (
    "https://statsapi.mlb.com/api/v1/stats"
    "?stats=season&playerPool=All&group=pitching"
    "&leagueIds=103,104&gameType=R"
    "&fields=stats,totalSplits,splits,stat,gamesPlayed,inningsPitched,"
    "saves,holds,stolenBases,player,fullName,id"
    "&limit=500&offset={offset}&season={season}"
)


def _cache_path(stat_type: str, season: int) -> str:
    """Build cache file path: .cache/{type}_{season}_{date}.parquet."""
    return os.path.join(CACHE_DIR, f"{stat_type}_{season}_{date.today().isoformat()}.parquet")


def _clean_old_caches(cache_dir: str, stat_type: str, season: int) -> None:
    """Remove old cache files for this stat_type/season (keep today's)."""
    today_name = f"{stat_type}_{season}_{date.today().isoformat()}.parquet"
    pattern = os.path.join(cache_dir, f"{stat_type}_{season}_*.parquet")
    for path in glob.glob(pattern):
        if os.path.basename(path) != today_name:
            os.remove(path)
            logger.debug(f"Removed old cache: {path}")


def _ip_to_dec(s) -> float:
    """Convert MLB API inningsPitched string (e.g. '45.2') to decimal innings."""
    try:
        parts = str(s).split('.')
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 3
        return float(s)
    except (ValueError, AttributeError):
        return 0.0


def _fetch_pitcher_stats_mlb(season: int) -> list[dict]:
    """Fetch season pitching stats from MLB Stats API, aggregated per player."""
    raw: dict[int, dict] = {}
    offset = 0
    while True:
        url = MLB_PITCHING_URL.format(season=season, offset=offset)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        splits = data.get('stats', [{}])[0].get('splits', [])
        if not splits:
            break

        for split in splits:
            player = split.get('player', {})
            stat = split.get('stat', {})
            pid = player.get('id')
            if pid is None:
                continue
            g = int(stat.get('gamesPlayed', 0) or 0)
            ip = _ip_to_dec(stat.get('inningsPitched', 0))
            sv = int(stat.get('saves', 0) or 0)
            hld = int(stat.get('holds', 0) or 0)
            sb = int(stat.get('stolenBases', 0) or 0)
            if pid not in raw:
                raw[pid] = {
                    'Name': player.get('fullName', ''),
                    'G': g, 'IP': ip, 'SV': sv, 'HLD': hld, 'SB': sb,
                }
            else:
                raw[pid]['G'] += g
                raw[pid]['IP'] += ip
                raw[pid]['SV'] += sv
                raw[pid]['HLD'] += hld
                raw[pid]['SB'] += sb

        total = data.get('stats', [{}])[0].get('totalSplits', 0)
        offset += len(splits)
        if offset >= total:
            break

    return list(raw.values())


def get_pitcher_stats(season: int) -> pd.DataFrame:
    """Fetch season pitching stats from MLB Stats API (cached daily).

    Returns DataFrame with columns: Name, G, IP, SV, HLD, SB
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path("pitching", season)

    if os.path.exists(path):
        logger.info(f"Reading cached pitching stats: {path}")
        return pd.read_parquet(path)

    logger.info(f"Fetching {season} pitching stats from MLB Stats API...")
    records = _fetch_pitcher_stats_mlb(season)
    df = pd.DataFrame(records, columns=["Name", "G", "IP", "SV", "HLD", "SB"])

    df.to_parquet(path, index=False)
    _clean_old_caches(CACHE_DIR, "pitching", season)
    logger.info(f"  Cached {len(df)} pitchers to {path}")
    return df


def get_batter_stats(season: int) -> pd.DataFrame:
    """Batter stats are not used in projections. Returns empty DataFrame."""
    return pd.DataFrame()


def get_player_stats(player_name: str, season: int) -> dict | None:
    """Look up a single pitcher's stats by name. Case-insensitive."""
    pitchers = get_pitcher_stats(season)
    match = pitchers[pitchers["Name"].str.lower() == player_name.lower()]
    if not match.empty:
        return match.iloc[0].to_dict()
    return None
