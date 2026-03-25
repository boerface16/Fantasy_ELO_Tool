"""pybaseball Statcast wrapper for daily ELO pipeline.

Regular Season (game_type == 'R') 데이터만 수집.
"""

import logging
from datetime import date, timedelta

import pandas as pd
from pybaseball import statcast

logger = logging.getLogger(__name__)


def get_yesterday() -> date:
    """어제 날짜 반환."""
    return date.today() - timedelta(days=1)


def fetch_statcast_date(target_date: date) -> pd.DataFrame:
    """특정 날짜의 Statcast 데이터를 가져와 Regular Season만 필터링.

    Args:
        target_date: 수집할 날짜

    Returns:
        Regular Season 투구 데이터 DataFrame. 데이터 없으면 empty DataFrame.
    """
    date_str = target_date.strftime('%Y-%m-%d')
    logger.info(f"Fetching Statcast data for {date_str}...")

    df = statcast(start_dt=date_str, end_dt=date_str)

    if df is None or df.empty:
        logger.info(f"  No data for {date_str}")
        return pd.DataFrame()

    # Regular Season 필터 (game_type == 'R')
    if 'game_type' in df.columns:
        df = df[df['game_type'] == 'R']
        logger.info(f"  Regular season filter: {len(df):,} pitches")
    else:
        logger.warning(f"  No game_type column — returning all {len(df):,} pitches")

    if df.empty:
        logger.info(f"  No regular season data for {date_str}")
        return pd.DataFrame()

    return df.reset_index(drop=True)


def fetch_statcast_range(start_date: date, end_date: date) -> pd.DataFrame:
    """날짜 범위의 Statcast 데이터를 가져와 Regular Season만 필터링.

    Args:
        start_date: 시작 날짜 (inclusive)
        end_date: 종료 날짜 (inclusive)

    Returns:
        Regular Season 투구 데이터 DataFrame. 데이터 없으면 empty DataFrame.
    """
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    logger.info(f"Fetching Statcast data for {start_str} ~ {end_str}...")

    df = statcast(start_dt=start_str, end_dt=end_str)

    if df is None or df.empty:
        logger.info(f"  No data for {start_str} ~ {end_str}")
        return pd.DataFrame()

    # Regular Season 필터
    if 'game_type' in df.columns:
        before = len(df)
        df = df[df['game_type'] == 'R']
        logger.info(f"  Regular season filter: {len(df):,} / {before:,} pitches")
    else:
        logger.warning(f"  No game_type column — returning all {len(df):,} pitches")

    if df.empty:
        logger.info(f"  No regular season data for range")
        return pd.DataFrame()

    return df.reset_index(drop=True)
