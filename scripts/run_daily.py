"""Daily pipeline orchestrator — runs all update steps in sequence.

Usage:
    python -m scripts.run_daily                                      # yesterday
    python -m scripts.run_daily --date 2026-04-15                   # specific date
    python -m scripts.run_daily --start-date 2026-03-27 --end-date 2026-04-15  # date range
    python -m scripts.run_daily --date 2026-04-15 --force           # reprocess

Steps per date:
    1. Player ELO + talent ELO (daily_pipeline) — handles 3B and GBS via Statcast
    2. Speed ELO supplement (MLB API box scores) — SB/CS events Statcast omits
    3. Team ELO (incremental backfill for target date)

Steps once (after all dates, using the final date's season):
    4. Refresh Fangraphs cache (batting + pitching stats)
    5. Refresh schedule cache (fetch this week's games)
    6. Refresh player season stats (for exact ESPN fantasy point leaderboard)
    7. Refresh advanced stats (xWOBA, WRC+, WAR, xFIP-, SIERA for stat line)
    8. Print summary
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
    parser.add_argument("--date", type=str, help="Single target date (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--start-date", type=str, help="Start of date range (YYYY-MM-DD), inclusive")
    parser.add_argument("--end-date", type=str, help="End of date range (YYYY-MM-DD), inclusive")
    parser.add_argument("--force", action="store_true", help="Re-process dates even if already processed")
    return parser.parse_args()


def _run_date(target: date, force: bool) -> dict:
    """Run ELO steps (1-3) for a single date. Returns per-step result dict."""
    results = {}

    logger.info("Step 1/3: Player ELO + Talent update...")
    try:
        from src.pipeline.daily_pipeline import run_daily_pipeline
        result = run_daily_pipeline(target_date=target, force=force)
        results["player_elo"] = result
        logger.info(f"  Status: {result['status']}")
        if result["status"] == "success":
            logger.info(f"  PAs: {result['pa_count']}, Players: {result['active_players']}")
    except Exception as e:
        results["player_elo"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    logger.info("Step 2/3: Speed ELO supplement (MLB API box scores)...")
    try:
        from src.etl.upload_to_supabase import get_supabase_client
        from src.engine.speed_elo_daily import run_speed_elo_for_date
        sb_client = get_supabase_client()
        result = run_speed_elo_for_date(target, sb_client)
        results["speed_elo"] = {"status": "success", **result}
        logger.info(
            f"  {result['players_updated']} players, "
            f"+{result['sb_applied']} SB, -{result['cs_applied']} CS"
        )
    except Exception as e:
        results["speed_elo"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    logger.info("Step 3/3: Team ELO update...")
    try:
        from scripts.backfill_team_elo import run_backfill
        run_backfill(target_date=target.isoformat())
        results["team_elo"] = {"status": "success"}
        logger.info("  Team ELO updated")
    except Exception as e:
        results["team_elo"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    return results


def _run_season_refreshes(season: int) -> dict:
    """Run season-level cache refreshes (steps 4-7). Returns per-step result dict."""
    results = {}

    logger.info("Step 4/7: Pitcher stats cache refresh...")
    try:
        from src.fantasy.fangraphs_enricher import get_pitcher_stats
        pitchers_df = get_pitcher_stats(season)
        results["pitcher_stats"] = {"status": "success", "pitchers": len(pitchers_df)}
        logger.info(f"  Cached {len(pitchers_df)} pitchers")
    except Exception as e:
        results["pitcher_stats"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    logger.info("Step 5/7: Schedule fetch...")
    try:
        from src.fantasy.schedule_fetcher import fetch_week_schedule
        games = fetch_week_schedule(date.today())
        results["schedule"] = {"status": "success", "games": len(games)}
        logger.info(f"  Fetched {len(games)} games for this week")
    except Exception as e:
        results["schedule"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    logger.info("Step 6/7: Player season stats refresh (MLB Stats API)...")
    try:
        from src.etl.fetch_player_stats import build_upsert_rows, upsert_rows
        from src.api.deps import get_supabase
        rows = build_upsert_rows(season)
        sb = get_supabase()
        count = upsert_rows(sb, rows)
        results["player_season_stats"] = {"status": "success", "rows": count}
        logger.info(f"  Upserted {count} player season stat rows")
    except Exception as e:
        results["player_season_stats"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    logger.info("Step 7/7: Advanced stats refresh (Statcast + Fangraphs)...")
    try:
        from src.etl.fetch_fangraphs_stats import build_rows, upsert_rows as upsert_fg_rows
        from src.api.deps import get_supabase as _get_sb
        adv_rows = build_rows(season)
        sb2 = _get_sb()
        adv_count = upsert_fg_rows(sb2, adv_rows)
        results["advanced_stats"] = {"status": "success", "rows": adv_count}
        logger.info(f"  Upserted {adv_count} advanced stat rows")
    except Exception as e:
        results["advanced_stats"] = {"status": "error", "error": str(e)}
        logger.error(f"  Failed: {e}")

    return results


def main():
    args = parse_args()

    # Build list of dates to process
    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            print("ERROR: --start-date and --end-date must both be provided for a range.")
            sys.exit(1)
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
        if start > end:
            print("ERROR: --start-date must be on or before --end-date.")
            sys.exit(1)
        targets = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    else:
        targets = [date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)]

    season = targets[-1].year
    range_label = targets[0].isoformat() if len(targets) == 1 else f"{targets[0].isoformat()} → {targets[-1].isoformat()}"

    print(f"\n{'=' * 60}")
    print(f"DAILY PIPELINE — {range_label} ({len(targets)} date(s))")
    print(f"{'=' * 60}\n")

    all_results: dict[str, dict] = {}

    # Per-date ELO steps
    for target in targets:
        if len(targets) > 1:
            print(f"\n--- {target.isoformat()} ---")
        date_results = _run_date(target, args.force)
        all_results[target.isoformat()] = date_results

    # Season-level refreshes — run once using the last date's season
    season_results = _run_season_refreshes(season)

    # Summary
    print(f"\n{'=' * 60}")
    print("DAILY PIPELINE SUMMARY")
    print(f"{'=' * 60}")
    if len(targets) > 1:
        for d, dr in all_results.items():
            statuses = [v.get("status", "?") for v in dr.values()]
            ok = all(s == "success" for s in statuses)
            step_summary = ", ".join(f"{k}={v.get('status', '?')}" for k, v in dr.items())
            print(f"  [{'OK' if ok else 'FAIL'}] {d}: {step_summary}")
    else:
        for step, data in list(all_results.values())[0].items():
            status = data.get("status", "unknown")
            icon = "OK" if status == "success" else "FAIL"
            print(f"  [{icon}] {step}: {status}")
            if status == "error":
                print(f"        {data.get('error', '')}")
    for step, data in season_results.items():
        status = data.get("status", "unknown")
        icon = "OK" if status == "success" else "FAIL"
        print(f"  [{icon}] {step}: {status}")
        if status == "error":
            print(f"        {data.get('error', '')}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
