"""Statcast 투구 데이터 → 타석(PA) 단위 변환."""

import pandas as pd
from src.etl.event_mapper import map_event


def convert_statcast_to_pa(statcast_df: pd.DataFrame) -> pd.DataFrame:
    # 1. PA만 추출 (events가 NOT NULL)
    pa_df = statcast_df[statcast_df['events'].notna()].copy()

    # 2. result_type 매핑
    pa_df['result_type'] = pa_df['events'].apply(map_event)

    # 3. 컬럼 변환
    pa_df['season_year'] = pa_df['game_year'] if 'game_year' in pa_df.columns else pd.to_datetime(pa_df['game_date']).dt.year
    pa_df['batter_id'] = pa_df['batter'].astype(int)
    pa_df['pitcher_id'] = pa_df['pitcher'].astype(int)
    pa_df['inning_half'] = pa_df['inning_topbot']
    pa_df['on_1b'] = pa_df['on_1b'].notna()
    pa_df['on_2b'] = pa_df['on_2b'].notna()
    pa_df['on_3b'] = pa_df['on_3b'].notna()
    pa_df['xwoba'] = pa_df.get('estimated_woba_using_speedangle')

    # 4. PA ID 생성
    pa_df['pa_id'] = pa_df['game_pk'].astype(int) * 1000 + pa_df['at_bat_number'].astype(int)

    # 5. 정렬
    pa_df = pa_df.sort_values(['game_date', 'game_pk', 'at_bat_number']).reset_index(drop=True)

    # 6. 출력 컬럼 선택
    output_columns = [
        'pa_id', 'game_pk', 'game_date', 'season_year',
        'batter_id', 'pitcher_id', 'result_type',
        'inning', 'inning_half', 'at_bat_number', 'outs_when_up',
        'on_1b', 'on_2b', 'on_3b',
        'home_team', 'away_team', 'bat_score', 'fld_score',
        'launch_speed', 'launch_angle', 'xwoba', 'delta_run_exp',
    ]
    return pa_df[output_columns]
