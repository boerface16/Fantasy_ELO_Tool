"""Backfill Team ELO from plate_appearances data.

Usage:
    python -m scripts.backfill_team_elo                        # full season
    python -m scripts.backfill_team_elo --date 2026-04-02      # single date (incremental)
    python -m scripts.backfill_team_elo --range 2026-04-01 2026-04-03  # date range
    python -m scripts.backfill_team_elo --fresh                # wipe + full recompute
"""

import argparse
import logging
import os
import sys
from dataclasses import asdict
from datetime import date, timedelta

import yaml
from dotenv import load_dotenv

# Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.team_elo_engine import TeamEloEngine, extract_game_results
from src.engine.preseason_projections import fetch_team_projected_wins
from src.etl.upload_to_supabase import get_supabase_client, upload_table

PA_COLUMNS = "pa_id,game_pk,game_date,home_team,away_team,bat_score,fld_score,inning_half"
PAGE_SIZE = 1000


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "team_elo_config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def fetch_pa_rows(client, date_filter: str | None = None, date_range: tuple[str, str] | None = None) -> list[dict]:
    """Fetch plate appearances from Supabase with pagination."""
    all_rows = []
    offset = 0

    while True:
        q = client.table("plate_appearances").select(PA_COLUMNS)
        if date_filter:
            q = q.eq("game_date", date_filter)
        elif date_range:
            q = q.gte("game_date", date_range[0]).lte("game_date", date_range[1])
        q = q.order("pa_id").range(offset, offset + PAGE_SIZE - 1)
        resp = q.execute()
        rows = resp.data or []
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    logger.info(f"Fetched {len(all_rows):,} plate appearances")
    return all_rows


def run_backfill(target_date: str | None = None, date_range: tuple[str, str] | None = None, fresh: bool = False):
    config = load_config()
    client = get_supabase_client()

    # --fresh: wipe existing team_elo data and recompute everything from scratch
    if fresh:
        logger.info("--fresh: deleting all team_elo records...")
        client.table("team_elo").delete().neq("team_code", "").execute()
        logger.info("Cleared team_elo table")
        # Force full recompute regardless of any date filter
        target_date = None
        date_range = None

    # Fetch PAs
    pa_rows = fetch_pa_rows(client, date_filter=target_date, date_range=date_range)
    if not pa_rows:
        logger.info("No plate appearances found for the given filter.")
        return

    # Extract game results
    games = extract_game_results(pa_rows)
    logger.info(f"Extracted {len(games):,} game results")

    if not games:
        logger.info("No valid game results extracted.")
        return

    # Fetch projected wins for season reset
    projected_wins = fetch_team_projected_wins()

    # For incremental updates, load prior ratings from most recent team_elo rows
    engine = TeamEloEngine(config, projected_wins=projected_wins)
    if target_date or date_range:
        _load_prior_ratings(client, engine)

    # Process
    engine.process_season(games)
    logger.info(f"Generated {len(engine.records):,} team ELO records")

    # Convert to dicts for upload
    records = [asdict(r) for r in engine.records]

    # Upload
    uploaded = upload_table(
        client, "team_elo", records,
        on_conflict="team_code,game_date,opponent_code,game_pk",
    )
    logger.info(f"Uploaded {uploaded:,} records to team_elo")

    # Summary
    print("\n" + "=" * 60)
    print("TEAM ELO BACKFILL SUMMARY")
    print("=" * 60)
    print(f"  Games processed: {len(games):,}")
    print(f"  Records uploaded: {uploaded:,}")
    print(f"  Teams: {len(engine.ratings)}")

    # Zero-sum check
    total_deviation = sum(elo - config["initial_elo"] for elo in engine.ratings.values())
    print(f"  Zero-sum check: {total_deviation:+.6f}")

    # Final rankings
    print("\n  Final Ratings:")
    for team, elo in sorted(engine.ratings.items(), key=lambda x: -x[1]):
        diff = elo - config["initial_elo"]
        print(f"    {team:4s}  {elo:7.1f}  ({diff:+.1f})")
    print("=" * 60)


def _load_prior_ratings(client, engine: TeamEloEngine):
    """Load most recent team ELO ratings for incremental processing."""
    resp = (
        client.table("team_elo")
        .select("team_code,elo_after,game_date")
        .order("game_date", desc=True)
        .limit(300)
        .execute()
    )
    seen = set()
    for row in (resp.data or []):
        tc = row["team_code"]
        if tc not in seen:
            seen.add(tc)
            engine.ratings[tc] = row["elo_after"]
    if seen:
        logger.info(f"Loaded prior ratings for {len(seen)} teams")


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill Team ELO")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"),
                        help="Date range (YYYY-MM-DD YYYY-MM-DD, inclusive)")
    parser.add_argument("--fresh", action="store_true",
                        help="Clear all team_elo data and recompute from scratch")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.fresh:
        run_backfill(fresh=True)
    elif args.range:
        run_backfill(date_range=(args.range[0], args.range[1]))
    elif args.date:
        run_backfill(target_date=args.date)
    else:
        # Full season backfill (no date filter)
        run_backfill()


if __name__ == "__main__":
    main()
