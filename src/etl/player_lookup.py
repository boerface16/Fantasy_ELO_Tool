"""MLB 선수 메타데이터 수집: MongoDB + Statcast fallback."""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def collect_player_ids(pa_df: pd.DataFrame) -> set[int]:
    """PA 데이터에서 batter + pitcher 고유 ID를 모두 수집."""
    batters = set(pa_df['batter'].dropna().astype(int).unique())
    pitchers = set(pa_df['pitcher'].dropna().astype(int).unique())
    return batters | pitchers


def determine_player_roles(pa_df: pd.DataFrame) -> dict[int, str]:
    """PA 데이터에서 각 선수의 역할 판별: batter/pitcher/two_way."""
    batters = set(pa_df['batter'].dropna().astype(int).unique())
    pitchers = set(pa_df['pitcher'].dropna().astype(int).unique())
    all_ids = batters | pitchers

    roles = {}
    for pid in all_ids:
        is_batter = pid in batters
        is_pitcher = pid in pitchers
        if is_batter and is_pitcher:
            roles[pid] = 'two_way'
        elif is_pitcher:
            roles[pid] = 'pitcher'
        else:
            roles[pid] = 'batter'
    return roles


def extract_pitcher_names_from_statcast(statcast_df: pd.DataFrame) -> dict[int, str]:
    """Statcast player_name 컬럼에서 pitcher_id → 'Last, First' 매핑 추출."""
    pitcher_names = (
        statcast_df[statcast_df['player_name'].notna()]
        .drop_duplicates('pitcher')[['pitcher', 'player_name']]
    )
    return dict(zip(
        pitcher_names['pitcher'].astype(int),
        pitcher_names['player_name'],
    ))


def parse_statcast_name(name: str) -> tuple[str, str]:
    """'Last, First' → (first_name, last_name)."""
    parts = name.split(', ', 1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return name.strip(), ''


def parse_mongo_player(doc: dict) -> dict:
    """MongoDB 문서를 player dict로 변환."""
    pid = int(doc['player_id'])
    full_name = doc.get('name', '')
    team = doc.get('current_team', '')

    # NaN/None 처리
    if not isinstance(full_name, str):
        full_name = ''
    if not isinstance(team, str):
        team = ''

    # 이름 분리: "First Last" 또는 "First Middle Last"
    parts = full_name.split(' ', 1)
    if len(parts) == 2:
        first_name = parts[0]
        last_name = parts[1]
    else:
        first_name = full_name
        last_name = ''

    return {
        'player_id': pid,
        'first_name': first_name,
        'last_name': last_name,
        'full_name': full_name,
        'team': team,
    }


def fetch_players_from_mongodb(player_ids: set[int], db) -> dict[int, dict]:
    """MongoDB mlb_transactions.players에서 선수 정보를 일괄 조회."""
    str_ids = [str(pid) for pid in player_ids]
    docs = db['players'].find(
        {'player_id': {'$in': str_ids}},
        {'_id': 0, 'player_id': 1, 'name': 1, 'current_team': 1},
    )
    results = {}
    for doc in docs:
        parsed = parse_mongo_player(doc)
        results[parsed['player_id']] = parsed
    logger.info(f"MongoDB: {len(results)}/{len(player_ids)} players found")
    return results


def build_players_dataframe(
    all_ids: set[int],
    api_results: dict[int, dict],
    statcast_names: dict[int, str],
) -> pd.DataFrame:
    """API/MongoDB 결과 + Statcast 이름으로 players DataFrame 구성.

    api_results가 있으면 우선 사용, 없으면 Statcast 이름으로 대체.
    """
    rows = []
    for pid in sorted(all_ids):
        if pid in api_results:
            row = {'player_id': pid, **api_results[pid]}
        elif pid in statcast_names:
            first, last = parse_statcast_name(statcast_names[pid])
            row = {
                'player_id': pid,
                'first_name': first,
                'last_name': last,
                'full_name': f"{first} {last}".strip(),
                'position': '',
            }
        else:
            row = {
                'player_id': pid,
                'first_name': '',
                'last_name': '',
                'full_name': '',
                'position': '',
            }
        rows.append(row)

    return pd.DataFrame(rows)
