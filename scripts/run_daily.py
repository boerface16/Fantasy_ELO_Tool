"""Daily pipeline orchestrator — runs all update steps in sequence.

Usage:
    python -m scripts.run_daily                    # yesterday
    python -m scripts.run_daily --date 2025-09-28  # specific date

Steps:
    1. Player ELO + talent ELO (daily_pipeline)
    2. Team ELO (incremental backfill for target date)
    3. Refresh schedule cache (fetch this week's games)
    4. Refresh Fangraphs cache (batting + pitching stats)
    5. Print summary
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

# Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def parse_args():
    parser = argparse.ArgumentParser(description="Daily Pipeline Orchestrator")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD, default: yesterday)")
    return parser.parse_args()


def main():
    args = parse_args()
    target = date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
    season = target.year

    results = {}
    print(f"\n{'=' * 60}")
    print(f"DAILY PIPELINE — {target.isoformat()}")
    print(f"{'=' * 60}\n")

    # Step 1: Player ELO + Talent
    logger.info("Step 1/4: Player ELO + Talent update...")
    try:
        from src.pipeline.daily_pipeline import run_daily_pipeline
        result = run_daily_pipeline(target_date=target)
        results["player_elo"] = result
        logger.info(f"  Status: {result['status']}")
        if result["status"] == "success":
            logger.info(f"  PAs: {result['pa_count']}, Players: {result['active_players']}")
    except Exception as e:
        results["player_elo"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    # Step 2: Team ELO
    logger.info("Step 2/4: Team ELO update...")
    try:
        from scripts.backfill_team_elo import run_backfill
        run_backfill(target_date=target.isoformat())
        results["team_elo"] = {"status": "success"}
        logger.info("  Team ELO updated")
    except Exception as e:
        results["team_elo"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    # Step 3: Refresh Fangraphs cache
    logger.info("Step 3/4: Fangraphs cache refresh...")
    try:
        from src.fantasy.fangraphs_enricher import get_batter_stats, get_pitcher_stats
        batters_df = get_batter_stats(season)
        pitchers_df = get_pitcher_stats(season)
        results["fangraphs"] = {
            "status": "success",
            "batters": len(batters_df),
            "pitchers": len(pitchers_df),
        }
        logger.info(f"  Cached {len(batters_df)} batters, {len(pitchers_df)} pitchers")
    except Exception as e:
        results["fangraphs"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    # Step 4: Refresh schedule cache
    logger.info("Step 4/4: Schedule fetch...")
    try:
        from src.fantasy.schedule_fetcher import fetch_week_schedule
        games = fetch_week_schedule(date.today())
        results["schedule"] = {"status": "success", "games": len(games)}
        logger.info(f"  Fetched {len(games)} games for this week")
    except Exception as e:
        results["schedule"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("DAILY PIPELINE SUMMARY")
    print(f"{'=' * 60}")
    for step, data in results.items():
        status = data.get("status", "unknown")
        icon = "OK" if status == "success" else "FAIL"
        print(f"  [{icon}] {step}: {status}")
        if status == "error":
            print(f"        {data.get('error', '')}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
