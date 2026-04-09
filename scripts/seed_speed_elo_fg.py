"""
Speed ELO utility — seed from MLB Stats API or backfill from Statcast.

Two modes:

  (default)  Seed speed ELO from MLB Stats API seasonal SB/CS totals using a
             z-score approach. Called daily by run_daily.py to keep speed ELO
             current with season-to-date stolen base rates.

  --backfill Re-process all existing game dates for a season (force=True) so
             that SB/CS PA rows are written with correct pa_ids and speed ELO
             is recomputed from pitch-by-pitch data. Run once after the pa_id
             collision bug fix, or to rebuild speed ELO from scratch.

Usage:
    python scripts/seed_speed_elo_fg.py --season 2026
    python scripts/seed_speed_elo_fg.py --season 2026 --dry-run
    python scripts/seed_speed_elo_fg.py --backfill --season 2026
"""

import argparse
import logging
import os
import sys

import numpy as np
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)

ELO_PER_SD = 100.0
ELO_BASE = 1500.0
ELO_MIN = 500.0
ELO_MAX = 3000.0
MIN_ATTEMPTS = 3

MLB_STATS_URL = (
    "https://statsapi.mlb.com/api/v1/stats"
    "?stats=season&playerPool=All&group=hitting"
    "&leagueIds=103,104&gameType=R"
    "&fields=stats,totalSplits,splits,stat,stolenBases,caughtStealing,"
    "plateAppearances,player,fullName,id"
    "&limit=500&offset={offset}&season={season}"
)


def fetch_mlb_sb_stats(season: int) -> list[dict]:
    """Fetch season SB/CS stats for all hitters from the MLB Stats API."""
    players = []
    offset = 0
    while True:
        url = MLB_STATS_URL.format(season=season, offset=offset)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        splits = data.get('stats', [{}])[0].get('splits', [])
        if not splits:
            break

        for split in splits:
            player = split.get('player', {})
            stat = split.get('stat', {})
            sb = int(stat.get('stolenBases', 0) or 0)
            cs = int(stat.get('caughtStealing', 0) or 0)
            pa = int(stat.get('plateAppearances', 0) or 0)
            players.append({
                'player_id': player.get('id'),
                'full_name': player.get('fullName', ''),
                'SB': sb,
                'CS': cs,
                'PA': pa,
                'attempts': sb + cs,
            })

        total = data.get('stats', [{}])[0].get('totalSplits', 0)
        offset += len(splits)
        if offset >= total:
            break

    # Aggregate across team stints (traded players appear once per team)
    merged: dict[int, dict] = {}
    for p in players:
        pid = p['player_id']
        if pid is None:
            continue
        if pid not in merged:
            merged[pid] = p.copy()
        else:
            merged[pid]['SB'] += p['SB']
            merged[pid]['CS'] += p['CS']
            merged[pid]['PA'] += p['PA']
            merged[pid]['attempts'] += p['attempts']

    return list(merged.values())


def compute_speed_elo(players: list[dict]) -> list[dict]:
    """Assign speed ELO via z-score on net speed score per 600 PA.

    Score = (SB * 1.0 + CS * -3.0) / PA * 600
    Mirrors the ELO engine's weight ratio (SB=+1, CS=-3) and normalizes
    by volume so high-frequency stealers rank above low-frequency ones.
    """
    for p in players:
        pa = max(p['PA'], 1)
        p['speed_score'] = (p['SB'] * 1.0 + p['CS'] * -3.0) / pa * 600

    qualified = [p for p in players if p['attempts'] >= MIN_ATTEMPTS]
    scores = [p['speed_score'] for p in qualified]
    mean_score = float(np.mean(scores)) if scores else 0.0
    std_score = float(np.std(scores)) if len(scores) > 1 else 5.0
    if std_score < 1e-6:
        std_score = 5.0

    for p in players:
        if p['attempts'] < MIN_ATTEMPTS:
            p['speed_elo'] = ELO_BASE
        else:
            z = (p['speed_score'] - mean_score) / std_score
            p['speed_elo'] = float(np.clip(ELO_BASE + z * ELO_PER_SD, ELO_MIN, ELO_MAX))

    return players


def run_speed_seed(season: int, sb_client=None) -> dict:
    """Seed speed ELO for the given season. Returns a result summary dict.

    Can be called from run_daily.py or standalone. If sb_client is not
    provided, one is created from env vars.
    """
    if sb_client is None:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
        sb_client = create_client(supabase_url, supabase_key)

    logger.info(f"Fetching MLB Stats API SB/CS data for {season}...")
    players = fetch_mlb_sb_stats(season)
    logger.info(f"  {len(players)} players fetched, {sum(1 for p in players if p['SB'] > 0)} with SB > 0")

    players = compute_speed_elo(players)

    # Fetch known player IDs to avoid FK violations (MLB API returns players not in our DB)
    known_ids: set[int] = set()
    offset = 0
    while True:
        rows = sb_client.table('players').select('player_id').range(offset, offset + 999).execute().data
        if not rows:
            break
        known_ids.update(r['player_id'] for r in rows)
        if len(rows) < 1000:
            break
        offset += 1000

    records = [
        {
            'player_id': int(p['player_id']),
            'player_role': 'batter',
            'talent_type': 'speed',
            'season_elo': p['speed_elo'],
            'career_elo': p['speed_elo'],
            'event_count': p['attempts'],
            'pa_count': p['PA'],
        }
        for p in players
        if p['player_id'] is not None and int(p['player_id']) in known_ids
    ]
    logger.info(f"  {len(records)} players matched to DB (filtered {len(players) - len(records)} unknown)")

    batch_size = 200
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        sb_client.table('talent_player_current').upsert(
            batch,
            on_conflict='player_id,talent_type,player_role'
        ).execute()

    logger.info(f"  Speed ELO upserted for {len(records)} players")
    return {'status': 'success', 'players_updated': len(records)}


def run_backfill(season: int) -> None:
    """Re-process all game dates for a season with force=True.

    Deletes and re-ingests each day's PAs so SB/CS rows are written with
    non-colliding pa_ids and speed ELO is recomputed from Statcast data.
    Processes dates chronologically so incremental talent ELO state is correct.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.etl.upload_to_supabase import get_supabase_client
    from src.pipeline.daily_pipeline import run_daily_pipeline
    from datetime import date as date_type

    client = get_supabase_client()
    rows = (
        client.table('plate_appearances')
        .select('game_date')
        .eq('season_year', season)
        .order('game_date')
        .execute()
        .data
    )
    dates = sorted({r['game_date'] for r in rows})

    if not dates:
        logger.info(f"No {season} game dates found in plate_appearances. Nothing to backfill.")
        return

    logger.info(f"Re-processing {len(dates)} dates: {dates[0]} -> {dates[-1]}")
    for d in dates:
        logger.info(f"--- {d} ---")
        result = run_daily_pipeline(date_type.fromisoformat(d), force=True)
        logger.info(
            f"  {d}: {result.get('status')}  "
            f"pa={result.get('pa_count', 0)}  "
            f"active_players={result.get('active_players', 0)}"
        )
    logger.info("Backfill complete.")


def main():
    parser = argparse.ArgumentParser(description='Speed ELO — seed from MLB Stats API or backfill from Statcast')
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--dry-run', action='store_true', help='Print results without writing to DB (seed mode only)')
    parser.add_argument('--backfill', action='store_true', help='Re-process existing game dates to rebuild speed ELO from Statcast')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')

    if args.backfill:
        run_backfill(args.season)
        return

    try:
        players = fetch_mlb_sb_stats(args.season)
    except Exception as e:
        print(f"ERROR fetching MLB Stats API: {e}")
        sys.exit(1)

    print(f"Total players fetched: {len(players)}")
    print(f"Players with SB > 0:  {sum(1 for p in players if p['SB'] > 0)}")

    players = compute_speed_elo(players)

    top20 = sorted([p for p in players if p['attempts'] >= MIN_ATTEMPTS],
                   key=lambda p: p['speed_elo'], reverse=True)[:20]
    print(f"\nTop 20 by Speed ELO:")
    for p in top20:
        print(f"  {p['full_name']:<25} SB={p['SB']:>3} CS={p['CS']:>2} "
              f"score={p['speed_score']:>6.2f}  ELO={p['speed_elo']:.0f}")

    if args.dry_run:
        print("\n[DRY RUN] No database writes.")
        return

    result = run_speed_seed(args.season)
    print(f"\nDone. Speed ELO seeded for {result['players_updated']} players.")


if __name__ == '__main__':
    main()
