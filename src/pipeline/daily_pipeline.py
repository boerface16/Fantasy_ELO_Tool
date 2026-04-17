"""Daily ELO Pipeline — 일일 증분 ELO 계산 오케스트레이터.

매일 자동으로 전일 Statcast 데이터를 가져와 증분 ELO를 계산하고 Supabase에 업로드.

Flow:
    1. Idempotency check (이미 처리된 날짜면 skip, force=True면 삭제 후 재처리)
    2. pybaseball fetch (Regular Season only)
    3. ETL: statcast_to_pa (기존 모듈 재사용)
    4. 신규 선수 감지 + 등록
    5. plate_appearances upsert
    6. 기존 ELO 상태 로드
    7. EloBatch(initial_states=...) → 증분 계산
    8. 결과 업로드: player_elo (active_only), elo_pa_detail, daily_ohlc
    9. Talent ELO: 9D 증분 계산 + 업로드
"""

import logging
from datetime import date

import numpy as np
import pandas as pd

from src.engine.elo_batch import EloBatch
from src.engine.elo_calculator import PlayerEloState
from src.engine.elo_config import INITIAL_ELO
from src.engine.re24_baseline import RE24Baseline
from src.engine.park_factor import ParkFactor
from src.engine.talent_batch import TalentBatch
from src.engine.talent_state_manager import DualBatterState, DualPitcherState, TalentStateManager
from src.engine.multi_elo_types import (
    BatterTalentState, PitcherTalentState, DEFAULT_ELO,
    BATTER_DIM_NAMES, BATTER_DIM_COUNT,
    PITCHER_DIM_NAMES, PITCHER_DIM_COUNT,
)
from src.engine.preseason_projections import (
    fetch_player_projections,
    projection_to_batter_elo,
    projection_to_pitcher_elo,
)
from src.etl.fetch_statcast import fetch_statcast_date
from src.etl.statcast_to_pa import convert_statcast_to_pa
from src.etl.player_registry import detect_new_player_ids_batch, register_new_players
from src.etl.upload_to_supabase import (
    get_supabase_client, upload_table, prepare_pa_records,
    prepare_pa_detail_records, prepare_ohlc_records,
)

logger = logging.getLogger(__name__)


def load_current_elo_states(client) -> dict[int, PlayerEloState]:
    """Supabase player_elo → PlayerEloState 복원.

    cumulative_rv는 0.0으로 리셋 (DB에 미저장, ELO 계산에 영향 없음).
    """
    logger.info("Loading current ELO states from Supabase...")
    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            client.table('player_elo')
            .select('player_id, composite_elo, pa_count, batting_elo, pitching_elo, batting_pa, pitching_pa')
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

    states = {}
    for row in all_rows:
        pid = row['player_id']
        states[pid] = PlayerEloState(
            player_id=pid,
            batting_elo=row.get('batting_elo', INITIAL_ELO) or INITIAL_ELO,
            pitching_elo=row.get('pitching_elo', INITIAL_ELO) or INITIAL_ELO,
            batting_pa=row.get('batting_pa', 0) or 0,
            pitching_pa=row.get('pitching_pa', 0) or 0,
            cumulative_rv=0.0,
        )

    logger.info(f"  Loaded {len(states):,} player ELO states")
    return states


def load_current_talent_states(client) -> tuple[dict[int, DualBatterState], dict[int, DualPitcherState]]:
    """Supabase talent_player_current → DualBatterState/DualPitcherState dicts."""
    logger.info("Loading current talent ELO states from Supabase...")
    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            client.table('talent_player_current')
            .select('player_id, player_role, talent_type, season_elo, career_elo, event_count, pa_count')
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

    batters: dict[int, DualBatterState] = {}
    pitchers: dict[int, DualPitcherState] = {}

    for row in all_rows:
        pid = row['player_id']
        role = row['player_role']
        talent_type = row['talent_type']
        season_elo = row.get('season_elo', DEFAULT_ELO) or DEFAULT_ELO
        career_elo = row.get('career_elo', DEFAULT_ELO) or DEFAULT_ELO
        event_count = row.get('event_count', 0) or 0
        pa_count = row.get('pa_count', 0) or 0

        if role == 'batter' and talent_type in BATTER_DIM_NAMES:
            if pid not in batters:
                batters[pid] = DualBatterState(player_id=pid)
            idx = BATTER_DIM_NAMES.index(talent_type)
            batters[pid].season.elo_dimensions[idx] = season_elo
            batters[pid].career.elo_dimensions[idx] = career_elo
            batters[pid].season.event_counts[idx] = event_count
            batters[pid].career.event_counts[idx] = event_count
            batters[pid].season.pa_count = pa_count
            batters[pid].career.pa_count = pa_count

        elif role == 'pitcher' and talent_type in PITCHER_DIM_NAMES:
            if pid not in pitchers:
                pitchers[pid] = DualPitcherState(player_id=pid)
            idx = PITCHER_DIM_NAMES.index(talent_type)
            pitchers[pid].season.elo_dimensions[idx] = season_elo
            pitchers[pid].career.elo_dimensions[idx] = career_elo
            pitchers[pid].season.event_counts[idx] = event_count
            pitchers[pid].career.event_counts[idx] = event_count
            pitchers[pid].season.bfp_count = pa_count
            pitchers[pid].career.bfp_count = pa_count

    logger.info(f"  Loaded {len(batters):,} talent batter states, {len(pitchers):,} talent pitcher states")
    return batters, pitchers


def _prepare_talent_pa_detail_records(details: list[dict]) -> list[dict]:
    """talent_pa_detail records for upload."""
    records = []
    for d in details:
        records.append({
            'pa_id': int(d['pa_id']),
            'player_id': int(d['player_id']),
            'player_role': d['player_role'],
            'talent_type': d['talent_type'],
            'elo_before': round(float(d['elo_before']), 4),
            'elo_after': round(float(d['elo_after']), 4),
            # delta is a GENERATED column — do not include
        })
    return records


def _prepare_talent_ohlc_records(ohlc_list: list[dict]) -> list[dict]:
    """talent_daily_ohlc records for upload."""
    records = []
    for ohlc in ohlc_list:
        records.append({
            'player_id': int(ohlc['player_id']),
            'game_date': ohlc['game_date'],
            'talent_type': ohlc['talent_type'],
            'elo_type': ohlc.get('elo_type', 'SEASON'),
            'open_elo': round(float(ohlc['open']), 4),
            'high_elo': round(float(ohlc['high']), 4),
            'low_elo': round(float(ohlc['low']), 4),
            'close_elo': round(float(ohlc['close']), 4),
            'total_pa': int(ohlc.get('total_pa', 0)),
        })
    return records


def _build_talent_reset_records(
    batters: dict,
    pitchers: dict,
) -> list[dict]:
    """Build talent_player_current records for ALL players after a season reset.

    Called once at season boundary so that inactive players get pa_count=0
    written to the DB rather than carrying last season's stale values.
    """
    records = []
    for pid, dual in batters.items():
        for b_idx, dim_name in enumerate(BATTER_DIM_NAMES):
            records.append({
                'player_id': pid,
                'player_role': 'batter',
                'talent_type': dim_name,
                'season_elo': round(float(dual.season.elo_dimensions[b_idx]), 4),
                'career_elo': round(float(dual.career.elo_dimensions[b_idx]), 4),
                'event_count': int(dual.season.event_counts[b_idx]),
                'pa_count': dual.season.pa_count,  # 0 after reset
            })
    for pid, dual in pitchers.items():
        for p_idx, dim_name in enumerate(PITCHER_DIM_NAMES):
            records.append({
                'player_id': pid,
                'player_role': 'pitcher',
                'talent_type': dim_name,
                'season_elo': round(float(dual.season.elo_dimensions[p_idx]), 4),
                'career_elo': round(float(dual.career.elo_dimensions[p_idx]), 4),
                'event_count': int(dual.season.event_counts[p_idx]),
                'pa_count': dual.season.bfp_count,  # 0 after reset
            })
    return records


def _detect_season_boundary(client, target_date: date) -> bool:
    """Check if target_date is the first game day of a new season.

    Checks player_elo.last_game_date first (reliable even without prior-year PAs),
    then falls back to plate_appearances. Returns True only when prior game data
    exists and its year is earlier than target_date.year — prevents a false True
    on a brand-new empty system.
    """
    # Primary: player_elo.last_game_date is always up-to-date after each run
    resp = (
        client.table("player_elo")
        .select("last_game_date")
        .not_.is_("last_game_date", "null")
        .order("last_game_date", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        last_year = int(resp.data[0]["last_game_date"][:4])
        return target_date.year > last_year

    # Fallback: plate_appearances
    resp2 = (
        client.table("plate_appearances")
        .select("game_date")
        .order("game_date", desc=True)
        .limit(1)
        .execute()
    )
    if not resp2.data:
        return False
    last_year = int(resp2.data[0]["game_date"][:4])
    return target_date.year > last_year


def _apply_talent_season_reset(
    batters: dict[int, DualBatterState],
    pitchers: dict[int, DualPitcherState],
    new_season: int,
) -> None:
    """Fetch projections and apply FiveThirtyEight-style reset to talent states."""
    logger.info(f"Season boundary detected — resetting talent ELO for {new_season}")

    # Fetch consensus projections
    bat_proj_elo = {}
    pit_proj_elo = {}
    try:
        bat_df = fetch_player_projections("bat")
        if bat_df is not None:
            bat_proj_elo = projection_to_batter_elo(bat_df)
    except Exception as e:
        logger.warning(f"Failed to fetch batter projections: {e}")

    try:
        pit_df = fetch_player_projections("pit")
        if pit_df is not None:
            pit_proj_elo = projection_to_pitcher_elo(pit_df)
    except Exception as e:
        logger.warning(f"Failed to fetch pitcher projections: {e}")

    # Apply reset via TalentStateManager
    mgr = TalentStateManager(initial_batters=batters, initial_pitchers=pitchers)
    mgr.reset_season(new_season, batter_projections=bat_proj_elo, pitcher_projections=pit_proj_elo)

    logger.info(
        f"  Reset complete: {len(bat_proj_elo)} batters with projections, "
        f"{len(pit_proj_elo)} pitchers with projections"
    )


def _apply_base_elo_season_reset(
    states: dict[int, PlayerEloState],
    new_season: int,
) -> None:
    """Apply FiveThirtyEight-style reset to base ELO states at season boundary."""
    logger.info(f"Season boundary detected — resetting base ELO for {new_season}")

    # Fetch projections and build composite projection per player
    bat_proj_elo = {}
    pit_proj_elo = {}
    try:
        bat_df = fetch_player_projections("bat")
        if bat_df is not None:
            for pid, elo_arr in projection_to_batter_elo(bat_df).items():
                bat_proj_elo[pid] = float(np.mean(elo_arr))
    except Exception as e:
        logger.warning(f"Failed to fetch batter projections for base ELO: {e}")

    try:
        pit_df = fetch_player_projections("pit")
        if pit_df is not None:
            for pid, elo_arr in projection_to_pitcher_elo(pit_df).items():
                pit_proj_elo[pid] = float(np.mean(elo_arr))
    except Exception as e:
        logger.warning(f"Failed to fetch pitcher projections for base ELO: {e}")

    reset_count = 0
    for pid, state in states.items():
        if state.batting_pa > 0 or state.pitching_pa > 0:
            state.reset_season(
                projected_batting=bat_proj_elo.get(pid),
                projected_pitching=pit_proj_elo.get(pid),
            )
            reset_count += 1

    logger.info(
        f"  Base ELO reset: {reset_count} players, "
        f"{len(bat_proj_elo)} batter projections, {len(pit_proj_elo)} pitcher projections"
    )


def delete_date_data(client, target_date: date):
    """날짜별 기존 데이터 삭제 (idempotent 재처리용).

    삭제 순서: elo_pa_detail → daily_ohlc → plate_appearances (FK 의존성).
    """
    date_str = target_date.isoformat()
    logger.info(f"Deleting existing data for {date_str}...")

    # 1. 해당 날짜 PA ID 목록 조회
    pa_ids = []
    offset = 0
    page_size = 1000
    while True:
        response = (
            client.table('plate_appearances')
            .select('pa_id')
            .eq('game_date', date_str)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data
        if not rows:
            break
        pa_ids.extend(r['pa_id'] for r in rows)
        offset += page_size
        if len(rows) < page_size:
            break

    if pa_ids:
        # 2. elo_pa_detail 삭제 (pa_id 기준)
        batch_size = 100
        for i in range(0, len(pa_ids), batch_size):
            batch = pa_ids[i:i + batch_size]
            client.table('elo_pa_detail').delete().in_('pa_id', batch).execute()
        logger.info(f"  Deleted {len(pa_ids)} elo_pa_detail records")

        # 2b. talent_pa_detail 삭제 (pa_id 기준)
        for i in range(0, len(pa_ids), batch_size):
            batch = pa_ids[i:i + batch_size]
            client.table('talent_pa_detail').delete().in_('pa_id', batch).execute()
        logger.info(f"  Deleted {len(pa_ids)} talent_pa_detail records")

    # 3. daily_ohlc 삭제 (game_date 기준)
    client.table('daily_ohlc').delete().eq('game_date', date_str).execute()
    logger.info(f"  Deleted daily_ohlc for {date_str}")

    # 3b. talent_daily_ohlc 삭제 (game_date 기준)
    client.table('talent_daily_ohlc').delete().eq('game_date', date_str).execute()
    logger.info(f"  Deleted talent_daily_ohlc for {date_str}")

    # 4. plate_appearances 삭제
    client.table('plate_appearances').delete().eq('game_date', date_str).execute()
    logger.info(f"  Deleted plate_appearances for {date_str}")



def run_daily_pipeline(target_date: date | None = None, force: bool = False) -> dict:
    """메인 파이프라인.

    Args:
        target_date: 처리할 날짜 (None이면 어제)
        force: True면 이미 처리된 날짜도 삭제 후 재처리

    Returns:
        dict with status and stats
    """
    from src.etl.fetch_statcast import get_yesterday

    if target_date is None:
        target_date = get_yesterday()

    date_str = target_date.isoformat()
    logger.info(f"=== Daily ELO Pipeline: {date_str} ===")

    client = get_supabase_client()

    # 1. Idempotency check — exclude synthetic speed rows (SB/CS/PKO) so their
    #    presence from backfill doesn't prevent real Statcast data from being loaded.
    existing = (
        client.table('plate_appearances')
        .select('pa_id', count='exact')
        .eq('game_date', date_str)
        .not_.in_('result_type', ['SB', 'CS', 'PKO'])
        .limit(1)
        .execute()
    )
    if existing.count and existing.count > 0:
        if force:
            logger.info(f"  Force mode: deleting existing {existing.count} PAs for {date_str}")
            delete_date_data(client, target_date)
        else:
            logger.info(f"  Already processed: {existing.count} PAs for {date_str}. Use --force to reprocess.")
            return {'status': 'already_processed', 'date': date_str, 'existing_pa_count': existing.count}

    # 2. Fetch Statcast
    statcast_df = fetch_statcast_date(target_date)
    if statcast_df.empty:
        logger.info(f"  No data for {date_str} (off-day or off-season)")
        return {'status': 'no_data', 'date': date_str}

    # 3. ETL: pitch → PA
    logger.info("  Converting pitches to plate appearances...")
    pa_df = convert_statcast_to_pa(statcast_df)
    logger.info(f"  {len(pa_df):,} plate appearances")

    if pa_df.empty:
        logger.info(f"  No PAs extracted for {date_str}")
        return {'status': 'no_pa', 'date': date_str}

    # 4. 신규 선수 감지 + 등록
    new_ids = detect_new_player_ids_batch(pa_df, client)
    new_player_count = 0
    if new_ids:
        new_player_count = register_new_players(new_ids, pa_df, client)

    # Detect season boundary BEFORE uploading PAs — once PAs are written, the
    # check would compare target_date.year against itself and always return False.
    is_new_season = _detect_season_boundary(client, target_date)

    # 5. plate_appearances upsert
    logger.info("  Uploading plate appearances...")
    pa_records = prepare_pa_records(pa_df)
    pa_uploaded = upload_table(client, 'plate_appearances', pa_records)

    # 6. 기존 ELO 상태 로드
    initial_states = load_current_elo_states(client)

    # Season boundary: apply base ELO reset if entering a new year
    if is_new_season:
        _apply_base_elo_season_reset(initial_states, target_date.year)

    # 7. 증분 ELO 계산
    logger.info("  Running incremental ELO calculation...")
    baseline = RE24Baseline()
    park_factor = ParkFactor()
    batch = EloBatch(
        re24_baseline=baseline,
        park_factor=park_factor,
        initial_states=initial_states,
    )
    batch.process(pa_df)

    # 8. 결과 업로드
    # 8a. player_elo (active_only=True → 당일 활동 선수만)
    logger.info("  Uploading player_elo (active only)...")
    player_records = batch.get_player_elo_records(active_only=True)
    elo_uploaded = upload_table(client, 'player_elo', player_records)

    # 8b. elo_pa_detail
    logger.info("  Uploading elo_pa_detail...")
    pa_detail_records = prepare_pa_detail_records(batch.pa_details)
    detail_uploaded = upload_table(client, 'elo_pa_detail', pa_detail_records)

    # 8c. daily_ohlc
    logger.info("  Uploading daily_ohlc...")
    ohlc_records = prepare_ohlc_records(batch.daily_ohlc)
    ohlc_uploaded = upload_table(client, 'daily_ohlc', ohlc_records,
                                 on_conflict='player_id,game_date,elo_type,role')

    # 9. Talent ELO (incremental 9D)
    logger.info("  Running incremental Talent ELO calculation...")
    initial_batters, initial_pitchers = load_current_talent_states(client)

    # Season boundary: apply projection-based reset, then flush ALL states so
    # inactive players get pa_count=0 rather than carrying last season's values.
    if is_new_season:
        _apply_talent_season_reset(initial_batters, initial_pitchers, target_date.year)
        logger.info("  Flushing season-reset talent states for all players...")
        reset_records = _build_talent_reset_records(initial_batters, initial_pitchers)
        upload_table(client, 'talent_player_current', reset_records)

    talent_batch = TalentBatch(initial_batters=initial_batters, initial_pitchers=initial_pitchers)
    talent_batch.process(pa_df)

    # 9a. talent_player_current (active_only=True)
    logger.info("  Uploading talent_player_current (active only)...")
    talent_player_records = talent_batch.get_talent_player_records(active_only=True)
    talent_player_uploaded = upload_table(client, 'talent_player_current', talent_player_records)

    # 9b. talent_pa_detail
    logger.info("  Uploading talent_pa_detail...")
    talent_detail_records = _prepare_talent_pa_detail_records(talent_batch.talent_pa_details)
    talent_detail_uploaded = upload_table(client, 'talent_pa_detail', talent_detail_records,
                                          on_conflict='pa_id,player_id,talent_type')

    # 9c. talent_daily_ohlc
    logger.info("  Uploading talent_daily_ohlc...")
    talent_ohlc_records = _prepare_talent_ohlc_records(talent_batch.talent_daily_ohlc)
    talent_ohlc_uploaded = upload_table(client, 'talent_daily_ohlc', talent_ohlc_records,
                                        on_conflict='player_id,game_date,talent_type,elo_type')

    result = {
        'status': 'success',
        'date': date_str,
        'pitches_fetched': len(statcast_df),
        'pa_count': len(pa_df),
        'new_players': new_player_count,
        'active_players': len(batch._active_player_ids),
        'pa_uploaded': pa_uploaded,
        'elo_uploaded': elo_uploaded,
        'detail_uploaded': detail_uploaded,
        'ohlc_uploaded': ohlc_uploaded,
        'talent_player_uploaded': talent_player_uploaded,
        'talent_detail_uploaded': talent_detail_uploaded,
        'talent_ohlc_uploaded': talent_ohlc_uploaded,
    }
    logger.info(f"  === Done: {result} ===")
    return result
