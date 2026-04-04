"""Statcast 투구 데이터 → 타석(PA) 단위 변환."""

import pandas as pd
from src.etl.event_mapper import map_event

# Statcast events that represent baserunning actions by a runner, not the batter
BASERUNNING_EVENTS = {
    'stolen_base_2b', 'stolen_base_3b', 'stolen_base_home',
    'caught_stealing_2b', 'caught_stealing_3b', 'caught_stealing_home',
    'pickoff_caught_stealing_2b', 'pickoff_caught_stealing_3b',
    'pickoff_caught_stealing_home',
}


def _get_runner_id(row) -> int | None:
    """Extract the runner's player ID for SB/CS events.

    For stolen_base/caught_stealing, the Statcast 'batter' column is the
    current plate batter — not the runner. The runner is identified by
    which base they started on.
    """
    event = row.get('events', '')
    if event in ('stolen_base_2b', 'caught_stealing_2b',
                 'pickoff_caught_stealing_2b'):
        val = row.get('on_1b')
        return int(val) if pd.notna(val) else None
    if event in ('stolen_base_3b', 'caught_stealing_3b',
                 'pickoff_caught_stealing_3b'):
        val = row.get('on_2b')
        return int(val) if pd.notna(val) else None
    if event in ('stolen_base_home', 'caught_stealing_home',
                 'pickoff_caught_stealing_home'):
        val = row.get('on_3b')
        return int(val) if pd.notna(val) else None
    return None


def _refine_bip_out(result_type: str, bb_type) -> str:
    """Refine generic OUT to POPUP or GROUNDOUT when bb_type is available."""
    if result_type != 'OUT' or not bb_type or pd.isna(bb_type):
        return result_type
    if bb_type == 'popup':
        return 'POPUP'
    if bb_type == 'ground_ball':
        return 'GROUNDOUT'
    return result_type  # fly_ball and line_drive remain OUT


def convert_statcast_to_pa(statcast_df: pd.DataFrame) -> pd.DataFrame:
    # 1. PA만 추출 (events가 NOT NULL)
    pa_df = statcast_df[statcast_df['events'].notna()].copy()

    # 2. result_type 매핑
    pa_df['result_type'] = pa_df['events'].apply(map_event)

    # 3. bb_type 추출 (BIP 타구 유형 — popup/ground_ball/fly_ball/line_drive)
    pa_df['bb_type'] = pa_df.get('bb_type')

    # 4. BIP out 세분화: OUT → POPUP 또는 GROUNDOUT
    pa_df['result_type'] = pa_df.apply(
        lambda r: _refine_bip_out(r['result_type'], r.get('bb_type')), axis=1
    )

    # 5. 주루 이벤트용 runner_id 추출 (SB/CS는 batter != runner)
    pa_df['runner_id'] = pa_df.apply(_get_runner_id, axis=1)

    # 6. 컬럼 변환
    pa_df['season_year'] = pa_df['game_year'] if 'game_year' in pa_df.columns else pd.to_datetime(pa_df['game_date']).dt.year
    pa_df['batter_id'] = pa_df['batter'].astype(int)
    pa_df['pitcher_id'] = pa_df['pitcher'].astype(int)
    pa_df['inning_half'] = pa_df['inning_topbot']
    pa_df['on_1b'] = pa_df['on_1b'].notna()
    pa_df['on_2b'] = pa_df['on_2b'].notna()
    pa_df['on_3b'] = pa_df['on_3b'].notna()
    pa_df['xwoba'] = pa_df.get('estimated_woba_using_speedangle')

    # 7. PA ID 생성
    pa_df['pa_id'] = pa_df['game_pk'].astype(int) * 1000 + pa_df['at_bat_number'].astype(int)

    # 8. 정렬
    pa_df = pa_df.sort_values(['game_date', 'game_pk', 'at_bat_number']).reset_index(drop=True)

    # 9. 출력 컬럼 선택
    output_columns = [
        'pa_id', 'game_pk', 'game_date', 'season_year',
        'batter_id', 'pitcher_id', 'result_type',
        'inning', 'inning_half', 'at_bat_number', 'outs_when_up',
        'on_1b', 'on_2b', 'on_3b',
        'home_team', 'away_team', 'bat_score', 'fld_score',
        'launch_speed', 'launch_angle', 'xwoba', 'delta_run_exp',
        'bb_type', 'runner_id',
    ]
    return pa_df[output_columns]
