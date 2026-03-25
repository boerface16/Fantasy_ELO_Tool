"""실제 Statcast 2025 데이터로 ETL 결과 검증."""

import pandas as pd
from src.etl.statcast_to_pa import convert_statcast_to_pa

STATCAST_PATH = '/Users/mksong/Documents/mlb-statcast-book/data/raw/statcast_2025.parquet'


def main():
    print("Loading Statcast 2025...")
    raw = pd.read_parquet(STATCAST_PATH)
    print(f"  Raw rows: {len(raw):,}")

    print("\nConverting to PA...")
    pa = convert_statcast_to_pa(raw)
    print(f"  PA rows: {len(pa):,}")

    print("\n--- result_type 분포 ---")
    print(pa['result_type'].value_counts().to_string())

    print(f"\n--- 기본 통계 ---")
    print(f"  Unique games: {pa['game_pk'].nunique():,}")
    print(f"  Unique batters: {pa['batter_id'].nunique():,}")
    print(f"  Unique pitchers: {pa['pitcher_id'].nunique():,}")
    print(f"  Date range: {pa['game_date'].min()} ~ {pa['game_date'].max()}")

    print(f"\n--- PA ID 유일성 ---")
    duplicates = pa['pa_id'].duplicated().sum()
    print(f"  Duplicate pa_id: {duplicates}")
    if duplicates > 0:
        print("  WARNING: PA ID 충돌 발견! game_pk * 1000 + at_bat_number 공식 재검토 필요")

    print(f"\n--- NULL 체크 ---")
    for col in ['pa_id', 'game_pk', 'batter_id', 'pitcher_id', 'result_type']:
        null_count = pa[col].isna().sum()
        print(f"  {col}: {null_count} nulls")

    # 로컬 저장 (검증용)
    output_path = 'data/plate_appearances_2025.parquet'
    pa.to_parquet(output_path, index=False)
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
