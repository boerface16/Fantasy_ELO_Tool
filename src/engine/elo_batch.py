"""
V5.3 ELO Batch Processor (MLB)

전체 시즌 PA를 시간순으로 처리하여 ELO를 계산하고
daily OHLC + PA detail을 생성.

Usage:
    batch = EloBatch()
    batch.process(pa_df)
    # Results:
    batch.players        → {player_id: PlayerEloState}
    batch.pa_details     → [dict, ...]  (elo_pa_detail 레코드)
    batch.daily_ohlc     → [DailyOhlc, ...]
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from src.engine.elo_config import INITIAL_ELO, K_FACTOR
from src.engine.elo_calculator import PlayerEloState, EloCalculator

logger = logging.getLogger(__name__)


@dataclass
class DailyOhlc:
    """일별 OHLC 데이터."""
    player_id: int
    game_date: date
    elo_type: str  # 'SEASON'
    open_elo: float
    high_elo: float
    low_elo: float
    close_elo: float
    games_played: int = 1
    total_pa: int = 0
    role: str = 'BATTING'  # 'BATTING' or 'PITCHING'

    @property
    def delta(self) -> float:
        return self.close_elo - self.open_elo

    @property
    def elo_range(self) -> float:
        return self.high_elo - self.low_elo


class EloBatch:
    """V5.3 ELO 배치 프로세서."""

    def __init__(self, k_factor: float = None, re24_baseline=None, park_factor=None,
                 initial_states: dict[int, PlayerEloState] = None):
        self.calc = EloCalculator(
            k_factor=k_factor or K_FACTOR,
            re24_baseline=re24_baseline,
            park_factor_obj=park_factor,
        )
        self.players: dict[int, PlayerEloState] = dict(initial_states) if initial_states else {}
        self.pa_details: list[dict] = []
        self.daily_ohlc: list[DailyOhlc] = []
        self._active_player_ids: set[int] = set()

        # OHLC 추적용 내부 상태 — 키: (player_id, role)
        self._current_date: Optional[str] = None
        self._day_open: dict[tuple[int, str], float] = {}
        self._day_high: dict[tuple[int, str], float] = {}
        self._day_low: dict[tuple[int, str], float] = {}
        self._day_pa: dict[tuple[int, str], int] = {}

    def _get_player(self, player_id: int) -> PlayerEloState:
        if player_id not in self.players:
            self.players[player_id] = PlayerEloState(player_id=player_id)
        return self.players[player_id]

    def _record_ohlc_open(self, player_id: int, role: str, elo: float):
        """하루의 첫 ELO를 Open으로 기록 (role별)."""
        key = (player_id, role)
        if key not in self._day_open:
            self._day_open[key] = elo
            self._day_high[key] = elo
            self._day_low[key] = elo
            self._day_pa[key] = 0

    def _update_ohlc(self, player_id: int, role: str, elo: float):
        """타석 후 High/Low/Close 업데이트 (role별)."""
        key = (player_id, role)
        if key in self._day_high:
            self._day_high[key] = max(self._day_high[key], elo)
        if key in self._day_low:
            self._day_low[key] = min(self._day_low[key], elo)
        if key in self._day_pa:
            self._day_pa[key] += 1

    def _finalize_day(self, game_date_str: str):
        """하루 종료 시 OHLC 레코드 생성 (role별)."""
        game_date_val = date.fromisoformat(game_date_str)
        for (player_id, role) in self._day_open:
            player = self._get_player(player_id)
            close_elo = player.batting_elo if role == 'BATTING' else player.pitching_elo
            self.daily_ohlc.append(DailyOhlc(
                player_id=player_id,
                game_date=game_date_val,
                elo_type='SEASON',
                open_elo=self._day_open[(player_id, role)],
                high_elo=self._day_high[(player_id, role)],
                low_elo=self._day_low[(player_id, role)],
                close_elo=close_elo,
                total_pa=self._day_pa.get((player_id, role), 0),
                role=role,
            ))
        self._day_open.clear()
        self._day_high.clear()
        self._day_low.clear()
        self._day_pa.clear()

    def process(self, pa_df: pd.DataFrame):
        """
        전체 PA DataFrame 처리.

        pa_df 컬럼: pa_id, game_pk, game_date, batter_id, pitcher_id,
                    result_type, delta_run_exp
        """
        total = len(pa_df)

        for idx, row in pa_df.iterrows():
            game_date_str = str(row['game_date'])[:10]

            # 날짜 변경 감지 → OHLC 저장
            if self._current_date is not None and game_date_str != self._current_date:
                self._finalize_day(self._current_date)
            self._current_date = game_date_str

            batter_id = int(row['batter_id'])
            pitcher_id = int(row['pitcher_id'])
            self._active_player_ids.add(batter_id)
            self._active_player_ids.add(pitcher_id)
            batter = self._get_player(batter_id)
            pitcher = self._get_player(pitcher_id)

            # OHLC open 기록 (타석 전, role별)
            self._record_ohlc_open(batter_id, 'BATTING', batter.batting_elo)
            self._record_ohlc_open(pitcher_id, 'PITCHING', pitcher.pitching_elo)

            # delta_run_exp (NaN → None)
            rv = row.get('delta_run_exp')
            if pd.isna(rv):
                rv = None

            # Base-out state encoding
            state = (int(bool(row.get('on_1b')))
                     + int(bool(row.get('on_2b'))) * 2
                     + int(bool(row.get('on_3b'))) * 4
                     + int(row.get('outs_when_up', 0)) * 8)

            home_team = row.get('home_team')
            result_type = row.get('result_type')

            # xwoba (NaN → None, 컬럼 없으면 None)
            xwoba_val = row.get('xwoba')
            if xwoba_val is not None and pd.isna(xwoba_val):
                xwoba_val = None

            # ELO 계산 (K-Modulation)
            result = self.calc.process_plate_appearance(
                batter, pitcher, rv,
                state=state,
                home_team=home_team,
                result_type=result_type,
                xwoba=xwoba_val,
            )

            # OHLC update (타석 후, role별)
            self._update_ohlc(batter_id, 'BATTING', batter.batting_elo)
            self._update_ohlc(pitcher_id, 'PITCHING', pitcher.pitching_elo)

            # PA detail 기록
            self.pa_details.append({
                'pa_id': int(row['pa_id']),
                'batter_id': batter_id,
                'pitcher_id': pitcher_id,
                'result_type': row['result_type'],
                'batter_elo_before': result.batter_elo_before,
                'batter_elo_after': result.batter_elo_after,
                'pitcher_elo_before': result.pitcher_elo_before,
                'pitcher_elo_after': result.pitcher_elo_after,
                'elo_delta': result.batter_delta,
                'k_base': result.k_base,
                'physics_mod': result.physics_mod,
                'k_effective': result.k_effective,
            })

            if (idx + 1) % 50000 == 0:
                logger.info(f"  Processed {idx + 1:,} / {total:,} PAs")

        # 마지막 날짜 OHLC 저장
        if self._current_date is not None:
            self._finalize_day(self._current_date)

        logger.info(f"  Completed {total:,} PAs, {len(self.daily_ohlc):,} OHLC records")

    def get_player_elo_records(self, active_only: bool = False) -> list[dict]:
        """player_elo 테이블용 레코드 생성.

        Args:
            active_only: True면 이번 실행에 활동한 선수만 반환 (daily pipeline용)
        """
        target_ids = self._active_player_ids if active_only else set(self.players.keys())
        records = []
        for pid, state in self.players.items():
            if pid not in target_ids:
                continue
            # 마지막 PA에서 last_game_date 추출
            last_date = None
            for detail in reversed(self.pa_details):
                if detail['batter_id'] == pid or detail['pitcher_id'] == pid:
                    # PA에서 game_date를 직접 가져올 수 없으므로 OHLC에서 추출
                    break

            # OHLC에서 마지막 날짜 찾기
            player_ohlc = [o for o in self.daily_ohlc if o.player_id == pid]
            if player_ohlc:
                last_date = max(o.game_date for o in player_ohlc).isoformat()

            records.append({
                'player_id': pid,
                'on_base_elo': state.elo,
                'power_elo': state.elo,
                'composite_elo': state.elo,
                'batting_elo': state.batting_elo,
                'pitching_elo': state.pitching_elo,
                'pa_count': state.pa_count,
                'batting_pa': state.batting_pa,
                'pitching_pa': state.pitching_pa,
                'last_game_date': last_date,
            })
        return records
