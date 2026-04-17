"""Plate appearances / Players DataFrame → Supabase 업로드."""

import os
import math
import time
import logging

import pandas as pd
from supabase import create_client

logger = logging.getLogger(__name__)


def get_supabase_client():
    url = os.environ['SUPABASE_URL']
    key = os.environ['SUPABASE_KEY']
    return create_client(url, key)


def prepare_player_records(players_df: pd.DataFrame) -> list[dict]:
    """Players DataFrame을 Supabase upsert용 dict 리스트로 변환."""
    records = players_df.to_dict('records')
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return records


def prepare_pa_records(pa_df: pd.DataFrame) -> list[dict]:
    """Plate appearances DataFrame을 Supabase upsert용 dict 리스트로 변환."""
    records = pa_df.to_dict('records')
    for r in records:
        # game_date → ISO string
        if hasattr(r.get('game_date'), 'isoformat'):
            r['game_date'] = r['game_date'].isoformat()[:10]
        # NaN → None
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
        # numpy int → Python int (JSON 직렬화)
        for k in ['pa_id', 'game_pk', 'season_year', 'batter_id', 'pitcher_id',
                   'inning', 'at_bat_number', 'outs_when_up', 'bat_score', 'fld_score', 'runner_id']:
            if r.get(k) is not None:
                r[k] = int(r[k])
    return records


def upload_table(client, table_name: str, records: list[dict], batch_size: int = 250,
                 on_conflict: str | None = None) -> int:
    """Supabase 테이블에 batch upsert.

    Args:
        on_conflict: UNIQUE constraint columns for conflict resolution
                     (e.g. 'player_id,game_date,elo_type,role').
                     Required for tables with SERIAL PK + separate UNIQUE constraint.
    """
    uploaded = 0
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        q = client.table(table_name).upsert(batch, on_conflict=on_conflict) if on_conflict else client.table(table_name).upsert(batch)
        # Retry up to 3 times on transient errors (e.g. statement timeout).
        for attempt in range(3):
            try:
                q.execute()
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                logger.warning(
                    f"  {table_name} batch {i}–{i + len(batch)} failed "
                    f"(attempt {attempt + 1}/3): {exc} — retrying in 3s"
                )
                time.sleep(3)
        uploaded += len(batch)
        if uploaded % 5000 == 0 or uploaded == total:
            logger.info(f"  {table_name}: {uploaded:,} / {total:,}")
    return uploaded


def prepare_pa_detail_records(pa_details: list[dict], elo_fields: bool = False) -> list[dict]:
    """Convert pa_details list to elo_pa_detail upsert records.

    Args:
        elo_fields: If True, include k_base/physics_mod/k_effective (run_elo.py full batch).
                    If False, omit them (daily_pipeline incremental update).
    """
    records = []
    for d in pa_details:
        rec = {
            'pa_id': int(d['pa_id']),
            'batter_id': int(d['batter_id']),
            'pitcher_id': int(d['pitcher_id']),
            'result_type': d['result_type'],
            'batter_elo_before': round(d['batter_elo_before'], 4),
            'batter_elo_after': round(d['batter_elo_after'], 4),
            'pitcher_elo_before': round(d['pitcher_elo_before'], 4),
            'pitcher_elo_after': round(d['pitcher_elo_after'], 4),
            'on_base_delta': round(d['elo_delta'], 4),
            'power_delta': 0.0,
        }
        if elo_fields:
            rec['k_base'] = round(d.get('k_base', 0.0), 4)
            rec['physics_mod'] = round(d.get('physics_mod', 1.0), 4)
            rec['k_effective'] = round(d.get('k_effective', 0.0), 4)
        records.append(rec)
    return records


def prepare_ohlc_records(daily_ohlc) -> list[dict]:
    """Convert daily_ohlc list to daily_ohlc upsert records."""
    records = []
    for ohlc in daily_ohlc:
        records.append({
            'player_id': int(ohlc.player_id),
            'game_date': ohlc.game_date.isoformat(),
            'elo_type': ohlc.elo_type,
            'open': round(ohlc.open_elo, 4),
            'high': round(ohlc.high_elo, 4),
            'low': round(ohlc.low_elo, 4),
            'close': round(ohlc.close_elo, 4),
            'games_played': ohlc.games_played,
            'total_pa': ohlc.total_pa,
            'role': ohlc.role,
        })
    return records


def upload_players(players_df: pd.DataFrame, batch_size: int = 500) -> int:
    client = get_supabase_client()
    records = prepare_player_records(players_df)
    logger.info(f"Uploading {len(records):,} players...")
    return upload_table(client, 'players', records, batch_size)


def upload_plate_appearances(pa_df: pd.DataFrame, batch_size: int = 1000) -> int:
    client = get_supabase_client()
    records = prepare_pa_records(pa_df)
    logger.info(f"Uploading {len(records):,} plate appearances...")
    return upload_table(client, 'plate_appearances', records, batch_size)
