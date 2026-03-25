"""Plate appearances / Players DataFrame → Supabase 업로드."""

import os
import math
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
                   'inning', 'at_bat_number', 'outs_when_up', 'bat_score', 'fld_score']:
            if r.get(k) is not None:
                r[k] = int(r[k])
    return records


def upload_table(client, table_name: str, records: list[dict], batch_size: int = 1000,
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
        q.execute()
        uploaded += len(batch)
        if uploaded % 5000 == 0 or uploaded == total:
            logger.info(f"  {table_name}: {uploaded:,} / {total:,}")
    return uploaded


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
