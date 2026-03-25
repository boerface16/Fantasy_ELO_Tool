"""신규 선수 감지 및 MLB Stats API를 통한 자동 등록.

PA 데이터에서 Supabase players 테이블에 없는 선수를 감지하고,
MLB Stats API로 메타데이터를 가져와 자동 등록.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def detect_new_player_ids_batch(pa_df, client) -> set[int]:
    """PA DataFrame의 batter/pitcher ID를 Supabase players와 비교하여 신규 ID 반환.

    Args:
        pa_df: plate_appearances DataFrame (batter_id, pitcher_id 컬럼 필요)
        client: Supabase client

    Returns:
        Supabase에 등록되지 않은 player_id set
    """
    # PA에서 모든 선수 ID 수집
    pa_ids = set()
    if 'batter_id' in pa_df.columns:
        pa_ids.update(pa_df['batter_id'].dropna().astype(int).unique())
    if 'pitcher_id' in pa_df.columns:
        pa_ids.update(pa_df['pitcher_id'].dropna().astype(int).unique())

    if not pa_ids:
        return set()

    # Supabase에서 기존 선수 ID 조회
    existing_ids = set()
    id_list = list(pa_ids)
    batch_size = 100
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        response = (
            client.table('players')
            .select('player_id')
            .in_('player_id', batch)
            .execute()
        )
        existing_ids.update(row['player_id'] for row in response.data)

    new_ids = pa_ids - existing_ids
    if new_ids:
        logger.info(f"  Detected {len(new_ids)} new player(s): {sorted(new_ids)[:10]}...")
    return new_ids


def fetch_player_from_mlb_api(player_id: int) -> Optional[dict]:
    """MLB Stats API에서 선수 정보를 가져온다.

    Args:
        player_id: MLB player ID

    Returns:
        선수 정보 dict 또는 None (API 실패 시)
    """
    url = f"{MLB_API_BASE}/people/{player_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        people = data.get('people', [])
        if not people:
            logger.warning(f"  MLB API: no data for player {player_id}")
            return None

        p = people[0]
        return {
            'player_id': player_id,
            'first_name': p.get('firstName', ''),
            'last_name': p.get('lastName', ''),
            'full_name': p.get('fullName', f'Player {player_id}'),
            'team': p.get('currentTeam', {}).get('abbreviation', ''),
            'position': p.get('primaryPosition', {}).get('abbreviation', ''),
        }
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning(f"  MLB API failed for player {player_id}: {e}")
        return None


def register_new_players(new_ids: set[int], pa_df, client) -> int:
    """신규 선수를 MLB API로 조회하여 Supabase players 테이블에 등록.

    Args:
        new_ids: 등록할 player ID set
        pa_df: PA DataFrame (fallback 이름 추출용)
        client: Supabase client

    Returns:
        등록된 선수 수
    """
    if not new_ids:
        return 0

    records = []
    for pid in sorted(new_ids):
        info = fetch_player_from_mlb_api(pid)
        if info:
            records.append(info)
        else:
            # Fallback: 최소 레코드 생성
            logger.info(f"  Fallback registration for player {pid}")
            records.append({
                'player_id': pid,
                'first_name': '',
                'last_name': '',
                'full_name': f'Player {pid}',
                'team': '',
                'position': '',
            })

    if records:
        # Batch upsert
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            client.table('players').upsert(batch).execute()

    logger.info(f"  Registered {len(records)} new player(s)")
    return len(records)
