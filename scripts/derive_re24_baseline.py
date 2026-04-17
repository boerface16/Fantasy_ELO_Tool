"""
RE24 / RE288 Baseline Derivation

Reads plate_appearances from Supabase and computes two run-expectancy tables:

  RE24  — average delta_run_exp per base-out state (24 states: 8 base configs × 3 out counts)
  RE288 — average delta_run_exp per base-out-count state (288 states: 24 × 12 ball-strike counts)
          Requires 'balls' and 'strikes' columns in plate_appearances. If missing, RE288 is skipped.

State encoding:
  base_out_state = int(on_1b) + int(on_2b)*2 + int(on_3b)*4 + outs*8   → 0–23
  count_state    = balls * 3 + strikes                                   → 0–11  (0-0 through 3-2)
  re288_state    = base_out_state * 12 + count_state                     → 0–287

Output:
  data/mlb_re24_baseline.csv
  data/mlb_re288_baseline.csv  (if balls/strikes available)

Usage:
    python -m scripts.derive_re24_baseline
"""

import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.etl.upload_to_supabase import get_supabase_client


# ── State name tables ─────────────────────────────────────────────────────────

BASE_OUT_NAMES = {
    0:  'Empty 0 Out',   1: '1B 0 Out',      2: '2B 0 Out',     3: '1B2B 0 Out',
    4:  '3B 0 Out',      5: '1B3B 0 Out',    6: '2B3B 0 Out',   7: 'Loaded 0 Out',
    8:  'Empty 1 Out',   9: '1B 1 Out',      10: '2B 1 Out',    11: '1B2B 1 Out',
    12: '3B 1 Out',      13: '1B3B 1 Out',   14: '2B3B 1 Out',  15: 'Loaded 1 Out',
    16: 'Empty 2 Out',   17: '1B 2 Out',     18: '2B 2 Out',    19: '1B2B 2 Out',
    20: '3B 2 Out',      21: '1B3B 2 Out',   22: '2B3B 2 Out',  23: 'Loaded 2 Out',
}

COUNT_NAMES = {
    0: '0-0', 1: '1-0', 2: '0-1',
    3: '2-0', 4: '1-1', 5: '0-2',
    6: '3-0', 7: '2-1', 8: '1-2',
    9: '3-1', 10: '2-2', 11: '3-2',
}


# ── Encoding helpers ──────────────────────────────────────────────────────────

def encode_base_out(on_1b, on_2b, on_3b, outs: int) -> int:
    return int(bool(on_1b)) + int(bool(on_2b)) * 2 + int(bool(on_3b)) * 4 + int(outs) * 8


def encode_count(balls: int, strikes: int) -> int:
    return int(balls) * 3 + int(strikes)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_pa_data(client, include_count: bool = False) -> pd.DataFrame:
    """Load PA data from Supabase using keyset pagination to avoid statement timeouts."""
    cols = 'pa_id, on_1b, on_2b, on_3b, outs_when_up, delta_run_exp'
    if include_count:
        cols += ', balls, strikes'

    print(f"Loading PA data (columns: {cols})...")

    PAGE_SIZE = 1000
    MAX_RETRIES = 3

    all_rows: list[dict] = []
    last_pa_id: int | None = None

    while True:
        q = (
            client.table('plate_appearances')
            .select(cols)
            .order('pa_id', desc=False)
            .limit(PAGE_SIZE)
        )
        if last_pa_id is not None:
            q = q.gt('pa_id', last_pa_id)

        rows = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                rows = q.execute().data
                break
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    raise
                print(f"  [warn] fetch failed (attempt {attempt}/{MAX_RETRIES}): {exc} — retrying in 2s")
                time.sleep(2)

        if not rows:
            break
        all_rows.extend(rows)
        last_pa_id = rows[-1]['pa_id']
        if len(rows) < PAGE_SIZE:
            break

    df = pd.DataFrame(all_rows)
    print(f"  Loaded {len(df):,} PAs")
    return df


# ── RE24 ──────────────────────────────────────────────────────────────────────

def compute_re24(df: pd.DataFrame) -> pd.DataFrame:
    """Compute mean delta_run_exp per base-out state (24 states)."""
    df = df.copy()
    df['state_id'] = df.apply(
        lambda r: encode_base_out(r['on_1b'], r['on_2b'], r['on_3b'], r['outs_when_up']),
        axis=1,
    )
    valid = df.dropna(subset=['delta_run_exp'])
    print(f"  RE24: {len(valid):,} valid PAs (with delta_run_exp)")

    grouped = (
        valid.groupby('state_id')['delta_run_exp']
        .agg(sample_count='count', mean_rv='mean', std_rv='std', median_rv='median')
        .reset_index()
    )
    grouped['state_name'] = grouped['state_id'].map(BASE_OUT_NAMES)
    grouped = grouped.sort_values('state_id')[
        ['state_id', 'state_name', 'sample_count', 'mean_rv', 'std_rv', 'median_rv']
    ]
    return grouped


# ── RE288 ─────────────────────────────────────────────────────────────────────

def compute_re288(df: pd.DataFrame) -> pd.DataFrame | None:
    """Compute mean delta_run_exp per base-out-count state (288 states).

    Returns None if balls/strikes columns are missing from the DataFrame.
    """
    if 'balls' not in df.columns or 'strikes' not in df.columns:
        print("  RE288: skipped — 'balls' and 'strikes' columns not found in plate_appearances")
        return None

    df = df.copy()
    valid = df.dropna(subset=['delta_run_exp', 'balls', 'strikes'])
    print(f"  RE288: {len(valid):,} valid PAs (with delta_run_exp + count)")

    valid['base_out_state'] = valid.apply(
        lambda r: encode_base_out(r['on_1b'], r['on_2b'], r['on_3b'], r['outs_when_up']),
        axis=1,
    )
    valid['count_state'] = valid.apply(
        lambda r: encode_count(r['balls'], r['strikes']), axis=1
    )
    valid['state_id'] = valid['base_out_state'] * 12 + valid['count_state']

    grouped = (
        valid.groupby(['base_out_state', 'count_state', 'state_id'])['delta_run_exp']
        .agg(sample_count='count', mean_rv='mean', std_rv='std', median_rv='median')
        .reset_index()
    )
    grouped['base_out_name'] = grouped['base_out_state'].map(BASE_OUT_NAMES)
    grouped['count_name'] = grouped['count_state'].map(COUNT_NAMES)
    grouped['state_name'] = grouped['base_out_name'] + ' | ' + grouped['count_name']
    grouped = grouped.sort_values('state_id')[
        ['state_id', 'state_name', 'base_out_state', 'base_out_name',
         'count_state', 'count_name', 'sample_count', 'mean_rv', 'std_rv', 'median_rv']
    ]
    return grouped


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("RE24 / RE288 Baseline Derivation")
    print("=" * 60)

    client = get_supabase_client()

    # Try to load with count columns; fall back silently if they don't exist
    try:
        df = load_pa_data(client, include_count=True)
        has_count = 'balls' in df.columns and df['balls'].notna().any()
    except Exception:
        df = load_pa_data(client, include_count=False)
        has_count = False

    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)

    # RE24
    print("\n--- RE24 ---")
    re24 = compute_re24(df)
    re24_path = os.path.join(data_dir, 'mlb_re24_baseline.csv')
    re24.to_csv(re24_path, index=False, float_format='%.6f')
    print(f"  Saved → {re24_path}")
    print(f"  Mean RV range: {re24['mean_rv'].min():.6f} to {re24['mean_rv'].max():.6f}")
    print(f"  Total PAs: {re24['sample_count'].sum():,}")
    print(re24.to_string(index=False))

    # RE288
    print("\n--- RE288 ---")
    re288 = compute_re288(df) if has_count else None
    if re288 is not None:
        re288_path = os.path.join(data_dir, 'mlb_re288_baseline.csv')
        re288.to_csv(re288_path, index=False, float_format='%.6f')
        print(f"  Saved → {re288_path}")
        print(f"  States populated: {len(re288)} / 288")
        print(f"  Total PAs: {re288['sample_count'].sum():,}")
        print(re288.to_string(index=False))
    else:
        print("  RE288 not computed (balls/strikes not available in plate_appearances).")
        print("  Add 'balls' and 'strikes' columns to the ETL to enable RE288.")


if __name__ == '__main__':
    main()
