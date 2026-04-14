"""Weekly cache refresh — regenerates Fangraphs stat caches.

Usage:
    python -m scripts.run_weekly                # current season
    python -m scripts.run_weekly --season 2025  # specific season
"""

import argparse
import logging
import os
import sys
from datetime import date

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def parse_args():
    parser = argparse.ArgumentParser(description="Weekly Cache Refresh")
    parser.add_argument("--season", type=int, default=date.today().year, help="Season year")
    return parser.parse_args()


def main():
    args = parse_args()
    season = args.season

    print(f"\n{'=' * 60}")
    print(f"WEEKLY CACHE REFRESH — {season} season")
    print(f"{'=' * 60}\n")

    from src.fantasy.fangraphs_enricher import get_pitcher_stats

    logger.info(f"Fetching {season} pitching stats...")
    pitchers = get_pitcher_stats(season)
    logger.info(f"  {len(pitchers)} pitchers cached")

    print(f"\n{'=' * 60}")
    print(f"  Pitchers: {len(pitchers)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
