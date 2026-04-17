"""
V5.3 ELO 전체 시즌 실행 파이프라인

1. Supabase에서 PA 데이터 로드
2. ELO 배치 계산
3. 결과 업로드 (player_elo, elo_pa_detail, daily_ohlc)
4. 검증

Usage:
    python -m scripts.run_elo
"""

import logging
import os
import sys

import pandas as pd
from dotenv import load_dotenv

# Setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.elo_batch import EloBatch
from src.engine.elo_config import INITIAL_ELO
from src.engine.re24_baseline import RE24Baseline
from src.engine.park_factor import ParkFactor
from src.engine.talent_batch import TalentBatch
from src.etl.upload_to_supabase import (
    get_supabase_client, upload_table,
    prepare_pa_detail_records, prepare_ohlc_records,
)


def load_pa_from_supabase(client) -> pd.DataFrame:
    """Supabase에서 전체 PA 데이터 로드 (정렬: game_date, pa_id).

    Uses keyset (cursor) pagination to avoid OFFSET-based full table scans,
    which time out at high offsets due to Supabase's statement timeout.
    Each page fetch is retried up to 3 times with 2s backoff on transient errors.
    """
    import time

    print("Loading PA data from Supabase...")

    COLUMNS = (
        'pa_id, game_pk, game_date, batter_id, pitcher_id, result_type, '
        'delta_run_exp, on_1b, on_2b, on_3b, outs_when_up, home_team'
    )
    PAGE_SIZE = 1000
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2  # seconds

    all_rows: list[dict] = []
    # Cursor tracks the last seen (game_date, pa_id) so the next page starts
    # strictly after that position, avoiding expensive OFFSET seeks.
    last_date: str | None = None
    last_pa_id: int | None = None

    while True:
        # --- build query for this page ---
        query = (
            client.table('plate_appearances')
            .select(COLUMNS)
            .order('game_date', desc=False)
            .order('pa_id', desc=False)
            .limit(PAGE_SIZE)
        )

        if last_date is not None:
            # Keyset filter: rows where (game_date, pa_id) > (last_date, last_pa_id).
            # PostgREST doesn't support tuple comparisons directly, so we use a
            # two-condition approach: either a later date, or same date with a
            # higher pa_id. The .or_() call translates to:
            #   game_date > last_date  OR  (game_date = last_date AND pa_id > last_pa_id)
            query = query.or_(
                f"game_date.gt.{last_date},"
                f"and(game_date.eq.{last_date},pa_id.gt.{last_pa_id})"
            )

        # --- fetch with retry ---
        rows = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = query.execute()
                rows = response.data
                break
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    raise
                print(
                    f"  [warn] page fetch failed (attempt {attempt}/{MAX_RETRIES}): {exc} "
                    f"— retrying in {RETRY_BACKOFF}s..."
                )
                time.sleep(RETRY_BACKOFF)

        if not rows:
            break

        all_rows.extend(rows)

        # Advance cursor to the last row of this page
        last_row = rows[-1]
        last_date = last_row['game_date']
        last_pa_id = last_row['pa_id']

        if len(rows) < PAGE_SIZE:
            # Partial page means we've reached the end of the table
            break

    df = pd.DataFrame(all_rows)
    print(f"  Loaded {len(df):,} PAs")
    return df



def print_summary(batch: EloBatch):
    """결과 요약."""
    print("\n" + "=" * 60)
    print("V5.3 ELO CALCULATION SUMMARY")
    print("=" * 60)

    players = batch.players

    print(f"\nPlayers: {len(players):,}")
    print(f"PA Details: {len(batch.pa_details):,}")
    print(f"OHLC Records: {len(batch.daily_ohlc):,}")

    # ELO distribution (composite)
    elos = [p.elo for p in players.values()]
    print(f"\nComposite ELO Distribution:")
    print(f"  Mean: {sum(elos) / len(elos):.1f}")
    print(f"  Min: {min(elos):.1f}")
    print(f"  Max: {max(elos):.1f}")

    # Standard deviation
    mean_elo = sum(elos) / len(elos)
    var = sum((e - mean_elo) ** 2 for e in elos) / len(elos)
    std = var ** 0.5
    print(f"  Std: {std:.1f}")

    # Zero-sum check (batting deltas + pitching deltas should net to 0)
    batting_delta = sum(p.batting_elo - INITIAL_ELO for p in players.values())
    pitching_delta = sum(p.pitching_elo - INITIAL_ELO for p in players.values())
    print(f"\nZero-Sum Check:")
    print(f"  Net batting ELO change: {batting_delta:+.2f}")
    print(f"  Net pitching ELO change: {pitching_delta:+.2f}")
    print(f"  Net total: {batting_delta + pitching_delta:+.2f}")

    # Top 10 batters (by batting_elo, batting_pa >= 100)
    top_batters = sorted(
        [(pid, p) for pid, p in players.items()
         if p.batting_pa >= 100],
        key=lambda x: -x[1].batting_elo
    )[:10]

    print(f"\nTop 10 Batters (Batting PA ≥ 100):")
    for pid, p in top_batters:
        print(f"  {pid}: batting_elo={p.batting_elo:.1f} (PA={p.batting_pa}, RV={p.cumulative_rv:+.1f})")

    # Top 10 pitchers (by pitching_elo, pitching_pa >= 100)
    top_pitchers = sorted(
        [(pid, p) for pid, p in players.items()
         if p.pitching_pa >= 100],
        key=lambda x: -x[1].pitching_elo
    )[:10]

    print(f"\nTop 10 Pitchers (Pitching PA ≥ 100):")
    for pid, p in top_pitchers:
        print(f"  {pid}: pitching_elo={p.pitching_elo:.1f} (BFP={p.pitching_pa}, RV={p.cumulative_rv:+.1f})")

    # Two-Way Players
    twp_players = [(pid, p) for pid, p in players.items()
                   if p.batting_pa > 0 and p.pitching_pa > 0]
    if twp_players:
        print(f"\nTwo-Way Players ({len(twp_players)}):")
        for pid, p in sorted(twp_players, key=lambda x: -x[1].elo):
            print(f"  {pid}: batting={p.batting_elo:.1f}({p.batting_pa}PA) pitching={p.pitching_elo:.1f}({p.pitching_pa}BFP) composite={p.elo:.1f}")


def main():
    print("=" * 60)
    print("V5.3 ELO Full Season Pipeline (State Norm + Park Factor)")
    print("=" * 60)

    # 1. Load PA data
    client = get_supabase_client()
    pa_df = load_pa_from_supabase(client)

    # 2. Load V5.3 support modules
    print("\nLoading V5.3 modules...")
    baseline = RE24Baseline()
    park_factor = ParkFactor()
    print(f"  RE24 baseline: loaded")
    print(f"  Park factors: {len(park_factor._park_factors)} teams")

    # 3. Run ELO calculation
    print("\nRunning ELO calculation (V5.3 state norm + park factor)...")
    batch = EloBatch(re24_baseline=baseline, park_factor=park_factor)
    batch.process(pa_df)

    # 3b. Run talent ELO calculation
    print("\nRunning 9D Talent ELO calculation...")
    talent_batch = TalentBatch()
    talent_batch.process(pa_df)
    print(f"  Talent PA details: {len(talent_batch.talent_pa_details):,}")
    print(f"  Talent OHLC records: {len(talent_batch.talent_daily_ohlc):,}")
    talent_records = talent_batch.get_talent_player_records()
    print(f"  Talent player records: {len(talent_records):,}")

    # 4. Summary
    print_summary(batch)

    # 5. Upload results
    print("\n" + "=" * 60)
    print("UPLOADING RESULTS TO SUPABASE")
    print("=" * 60)

    # 5a. player_elo
    print("\n--- player_elo ---")
    player_records = batch.get_player_elo_records()
    n = upload_table(client, 'player_elo', player_records, batch_size=500)
    print(f"  Uploaded: {n:,}")

    # 5b. elo_pa_detail
    print("\n--- elo_pa_detail ---")
    pa_detail_records = prepare_pa_detail_records(batch.pa_details, elo_fields=True)
    n = upload_table(client, 'elo_pa_detail', pa_detail_records, batch_size=1000)
    print(f"  Uploaded: {n:,}")

    # 5c. daily_ohlc
    print("\n--- daily_ohlc ---")
    ohlc_records = prepare_ohlc_records(batch.daily_ohlc)
    n = upload_table(client, 'daily_ohlc', ohlc_records, batch_size=1000,
                     on_conflict='player_id,game_date,elo_type,role')
    print(f"  Uploaded: {n:,}")

    # 5d. talent_player_current
    print("\n--- talent_player_current ---")
    n = upload_table(client, 'talent_player_current', talent_records, batch_size=1000)
    print(f"  Uploaded: {n:,}")

    # 5e. talent_pa_detail
    print("\n--- talent_pa_detail ---")
    talent_pa_records = [{
        'pa_id': d['pa_id'],
        'player_id': d['player_id'],
        'player_role': d['player_role'],
        'talent_type': d['talent_type'],
        'elo_before': round(d['elo_before'], 4),
        'elo_after': round(d['elo_after'], 4),
    } for d in talent_batch.talent_pa_details]
    n = upload_table(client, 'talent_pa_detail', talent_pa_records, batch_size=1000,
                     on_conflict='pa_id,player_id,talent_type')
    print(f"  Uploaded: {n:,}")

    # 5f. talent_daily_ohlc
    print("\n--- talent_daily_ohlc ---")
    talent_ohlc_records = [{
        'player_id': o['player_id'],
        'game_date': o['game_date'],
        'talent_type': o['talent_type'],
        'elo_type': o['elo_type'],
        'open_elo': round(o['open'], 4),
        'high_elo': round(o['high'], 4),
        'low_elo': round(o['low'], 4),
        'close_elo': round(o['close'], 4),
        'total_pa': o['total_pa'],
    } for o in talent_batch.talent_daily_ohlc]
    n = upload_table(client, 'talent_daily_ohlc', talent_ohlc_records, batch_size=1000,
                     on_conflict='player_id,game_date,talent_type,elo_type')
    print(f"  Uploaded: {n:,}")

    # 6. Verify
    print("\n--- Verification ---")
    r = client.table('player_elo').select('player_id', count='exact').execute()
    print(f"  player_elo: {r.count} rows")
    r = client.table('elo_pa_detail').select('pa_id', count='exact').execute()
    print(f"  elo_pa_detail: {r.count} rows")
    r = client.table('daily_ohlc').select('id', count='exact').execute()
    print(f"  daily_ohlc: {r.count} rows")
    r = client.table('talent_player_current').select('player_id', count='exact').execute()
    print(f"  talent_player_current: {r.count} rows")
    try:
        r = client.table('talent_pa_detail').select('id', count='exact').execute()
        print(f"  talent_pa_detail: {r.count} rows")
    except Exception:
        print(f"  talent_pa_detail: (count unavailable — table too large)")
    try:
        r = client.table('talent_daily_ohlc').select('id', count='exact').execute()
        print(f"  talent_daily_ohlc: {r.count} rows")
    except Exception:
        print(f"  talent_daily_ohlc: (count unavailable — table too large)")

    print("\nDone!")


if __name__ == '__main__':
    main()
