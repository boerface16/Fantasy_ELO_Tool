"""Fangraphs stats enricher — pybaseball wrapper with daily file cache.

Fetches season-level batting/pitching stats from Fangraphs via pybaseball,
caches results as parquet files in .cache/ to avoid repeated API calls.
"""

import glob
import logging
import os
from datetime import date

import pandas as pd
from pybaseball import batting_stats, pitching_stats

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache")

BATTER_COLS = ["Name", "Team", "PA", "wRC+", "ISO", "BB%", "K%", "wOBA", "OPS"]
PITCHER_COLS = ["Name", "Team", "IP", "ERA", "FIP", "WHIP", "K/9", "BB/9", "ERA-"]


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


def _filter_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Keep only columns that exist in the DataFrame."""
    available = [c for c in cols if c in df.columns]
    return df[available].copy()


def get_batter_stats(season: int) -> pd.DataFrame:
    """Fetch season batting stats from Fangraphs (cached daily).

    Args:
        season: MLB season year (e.g. 2025)

    Returns:
        DataFrame with key batting columns
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path("batting", season)

    if os.path.exists(path):
        logger.info(f"Reading cached batting stats: {path}")
        return pd.read_parquet(path)

    logger.info(f"Fetching {season} batting stats from Fangraphs...")
    df = batting_stats(season, season)
    df = _filter_cols(df, BATTER_COLS)

    df.to_parquet(path, index=False)
    _clean_old_caches(CACHE_DIR, "batting", season)
    logger.info(f"  Cached {len(df)} batters to {path}")
    return df


def get_pitcher_stats(season: int) -> pd.DataFrame:
    """Fetch season pitching stats from Fangraphs (cached daily).

    Args:
        season: MLB season year (e.g. 2025)

    Returns:
        DataFrame with key pitching columns
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path("pitching", season)

    if os.path.exists(path):
        logger.info(f"Reading cached pitching stats: {path}")
        return pd.read_parquet(path)

    logger.info(f"Fetching {season} pitching stats from Fangraphs...")
    df = pitching_stats(season, season)
    df = _filter_cols(df, PITCHER_COLS)

    df.to_parquet(path, index=False)
    _clean_old_caches(CACHE_DIR, "pitching", season)
    logger.info(f"  Cached {len(df)} pitchers to {path}")
    return df


def get_player_stats(player_name: str, season: int) -> dict | None:
    """Look up a single player's Fangraphs stats.

    Searches batting stats first, then pitching. Case-insensitive match.

    Args:
        player_name: player full name
        season: MLB season year

    Returns:
        dict of stats or None if not found
    """
    # Try batting
    batters = get_batter_stats(season)
    match = batters[batters["Name"].str.lower() == player_name.lower()]
    if not match.empty:
        return match.iloc[0].to_dict()

    # Try pitching
    pitchers = get_pitcher_stats(season)
    match = pitchers[pitchers["Name"].str.lower() == player_name.lower()]
    if not match.empty:
        return match.iloc[0].to_dict()

    return None
