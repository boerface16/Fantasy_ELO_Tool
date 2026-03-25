"""
RE24 Baseline 계산 스크립트

Supabase plate_appearances에서 base-out state별 평균 delta_run_exp를 계산하여
data/mlb_re24_baseline.csv에 저장.

State encoding:
  state = int(on_1b) + int(on_2b)*2 + int(on_3b)*4 + outs*8
  → 0~23 (8 base states × 3 out states)

Usage:
    python -m scripts.derive_re24_baseline
"""

import os
import sys

import pandas as pd
from dotenv import load_dotenv

# Setup
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.etl.upload_to_supabase import get_supabase_client


STATE_NAMES = {
    0: 'Empty 0Out',
    1: '1B 0Out',
    2: '2B 0Out',
    3: '1B2B 0Out',
    4: '3B 0Out',
    5: '1B3B 0Out',
    6: '2B3B 0Out',
    7: 'Loaded 0Out',
    8: 'Empty 1Out',
    9: '1B 1Out',
    10: '2B 1Out',
    11: '1B2B 1Out',
    12: '3B 1Out',
    13: '1B3B 1Out',
    14: '2B3B 1Out',
    15: 'Loaded 1Out',
    16: 'Empty 2Out',
    17: '1B 2Out',
    18: '2B 2Out',
    19: '1B2B 2Out',
    20: '3B 2Out',
    21: '1B3B 2Out',
    22: '2B3B 2Out',
    23: 'Loaded 2Out',
}


def encode_base_out_state(on_1b, on_2b, on_3b, outs: int) -> int:
    """Base-out state를 0~23 정수로 인코딩."""
    return int(bool(on_1b)) + int(bool(on_2b)) * 2 + int(bool(on_3b)) * 4 + outs * 8


def load_pa_data(client) -> pd.DataFrame:
    """Supabase에서 PA 데이터 로드 (state 계산에 필요한 컬럼만)."""
    print("Loading PA data from Supabase...")

    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            client.table('plate_appearances')
            .select('on_1b, on_2b, on_3b, outs_when_up, delta_run_exp')
            .order('pa_id')
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data
        if not rows:
            break
        all_rows.extend(rows)
        offset += page_size
        if len(rows) < page_size:
            break

    df = pd.DataFrame(all_rows)
    print(f"  Loaded {len(df):,} PAs")
    return df


def compute_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """State별 평균 delta_run_exp 계산."""
    # State 인코딩
    df['state_id'] = df.apply(
        lambda r: encode_base_out_state(r['on_1b'], r['on_2b'], r['on_3b'], int(r['outs_when_up'])),
        axis=1
    )

    # delta_run_exp가 None/NaN인 행 제외
    valid = df.dropna(subset=['delta_run_exp'])
    print(f"  Valid PAs (with delta_run_exp): {len(valid):,}")

    # State별 통계
    grouped = valid.groupby('state_id')['delta_run_exp'].agg(
        sample_count='count',
        mean_rv='mean',
        std_rv='std',
        median_rv='median',
    ).reset_index()

    # State 이름 추가
    grouped['state_name'] = grouped['state_id'].map(STATE_NAMES)

    # 정렬 및 컬럼 순서
    grouped = grouped.sort_values('state_id')
    grouped = grouped[['state_id', 'state_name', 'sample_count', 'mean_rv', 'std_rv', 'median_rv']]

    return grouped


def main():
    print("=" * 60)
    print("RE24 Baseline Derivation")
    print("=" * 60)

    client = get_supabase_client()
    df = load_pa_data(client)
    baseline = compute_baseline(df)

    # Save
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'mlb_re24_baseline.csv')
    baseline.to_csv(output_path, index=False, float_format='%.6f')
    print(f"\nSaved to {output_path}")

    # Display
    print(f"\nRE24 Baseline ({len(baseline)} states):")
    print(baseline.to_string(index=False))

    # Summary
    print(f"\nMean RV range: {baseline['mean_rv'].min():.6f} to {baseline['mean_rv'].max():.6f}")
    print(f"Total PAs: {baseline['sample_count'].sum():,}")


if __name__ == '__main__':
    main()
