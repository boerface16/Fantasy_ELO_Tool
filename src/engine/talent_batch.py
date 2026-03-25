"""Talent Batch Processor — 9D talent ELO batch computation.

Processes PA DataFrame to produce:
- talent_pa_details: per-PA per-dimension ELO changes
- talent_daily_ohlc: daily OHLC per dimension
- talent_player_records: current snapshot per dimension
"""
import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.engine.multi_elo_config import MultiEloConfig
from src.engine.multi_elo_engine import MultiEloEngine
from src.engine.multi_elo_types import (
    BatterTalentState,
    PitcherTalentState,
    BATTER_DIM_NAMES,
    PITCHER_DIM_NAMES,
    DEFAULT_ELO,
)
from src.engine.talent_state_manager import TalentStateManager, DualBatterState, DualPitcherState

logger = logging.getLogger(__name__)


class TalentBatch:
    """9D Talent ELO batch processor."""

    def __init__(
        self,
        config: MultiEloConfig | None = None,
        initial_batters: dict[int, DualBatterState] | None = None,
        initial_pitchers: dict[int, DualPitcherState] | None = None,
    ):
        self.config = config or MultiEloConfig()
        self.engine = MultiEloEngine(config=self.config)
        self.state_mgr = TalentStateManager(
            initial_batters=initial_batters,
            initial_pitchers=initial_pitchers,
        )

        self.talent_pa_details: list[dict] = []
        self.talent_daily_ohlc: list[dict] = []
        self._active_player_ids: set[int] = set()

        # OHLC tracking: key = (player_id, talent_type)
        self._current_date: Optional[str] = None
        self._day_open: dict[tuple, float] = {}
        self._day_high: dict[tuple, float] = {}
        self._day_low: dict[tuple, float] = {}
        self._day_pa_count: dict[tuple, int] = {}

    def _record_ohlc_open(self, player_id: int, talent_type: str, elo: float):
        key = (player_id, talent_type)
        if key not in self._day_open:
            self._day_open[key] = elo
            self._day_high[key] = elo
            self._day_low[key] = elo
            self._day_pa_count[key] = 0

    def _update_ohlc(self, player_id: int, talent_type: str, elo: float):
        key = (player_id, talent_type)
        if key in self._day_high:
            self._day_high[key] = max(self._day_high[key], elo)
        if key in self._day_low:
            self._day_low[key] = min(self._day_low[key], elo)
        if key in self._day_pa_count:
            self._day_pa_count[key] += 1

    def _finalize_day(self, game_date_str: str):
        game_date_val = date.fromisoformat(game_date_str)
        for (player_id, talent_type) in list(self._day_open.keys()):
            # Get current ELO for close value
            close_elo = self._get_current_elo(player_id, talent_type)
            self.talent_daily_ohlc.append({
                'player_id': player_id,
                'game_date': game_date_val.isoformat(),
                'talent_type': talent_type,
                'elo_type': 'SEASON',
                'open': self._day_open[(player_id, talent_type)],
                'high': self._day_high[(player_id, talent_type)],
                'low': self._day_low[(player_id, talent_type)],
                'close': close_elo,
                'total_pa': self._day_pa_count.get((player_id, talent_type), 0),
            })
        self._day_open.clear()
        self._day_high.clear()
        self._day_low.clear()
        self._day_pa_count.clear()

    def _get_current_elo(self, player_id: int, talent_type: str) -> float:
        """Get current ELO for a player's talent dimension."""
        if talent_type in BATTER_DIM_NAMES:
            idx = BATTER_DIM_NAMES.index(talent_type)
            if player_id in self.state_mgr.all_batters:
                return float(self.state_mgr.all_batters[player_id].season.elo_dimensions[idx])
        if talent_type in PITCHER_DIM_NAMES:
            idx = PITCHER_DIM_NAMES.index(talent_type)
            if player_id in self.state_mgr.all_pitchers:
                return float(self.state_mgr.all_pitchers[player_id].season.elo_dimensions[idx])
        return DEFAULT_ELO

    def process(self, pa_df: pd.DataFrame):
        """Process PA DataFrame for 9D talent ELO."""
        total = len(pa_df)

        for idx, row in pa_df.iterrows():
            game_date_str = str(row['game_date'])[:10]

            if self._current_date is not None and game_date_str != self._current_date:
                self._finalize_day(self._current_date)
            self._current_date = game_date_str

            batter_id = int(row['batter_id'])
            pitcher_id = int(row['pitcher_id'])
            result_type = row.get('result_type', 'OUT')

            self._active_player_ids.add(batter_id)
            self._active_player_ids.add(pitcher_id)

            batter_dual = self.state_mgr.get_or_create_batter(batter_id)
            pitcher_dual = self.state_mgr.get_or_create_pitcher(pitcher_id)

            batter = batter_dual.season
            pitcher = pitcher_dual.season

            # RISP from base state
            is_risp = bool(row.get('on_2b', False)) or bool(row.get('on_3b', False))

            # Record OHLC opens (before PA)
            for b_idx, dim_name in enumerate(BATTER_DIM_NAMES):
                self._record_ohlc_open(batter_id, dim_name, float(batter.elo_dimensions[b_idx]))
            for p_idx, dim_name in enumerate(PITCHER_DIM_NAMES):
                self._record_ohlc_open(pitcher_id, dim_name, float(pitcher.elo_dimensions[p_idx]))

            # Snapshot before
            batter_before = batter.elo_dimensions.copy()
            pitcher_before = pitcher.elo_dimensions.copy()

            # Process PA (engine mutates batter/pitcher season state in place)
            result = self.engine.process_plate_appearance(
                batter, pitcher,
                result_type=result_type,
                is_risp=is_risp,
            )

            # Apply same deltas to career
            batter_dual.career.apply_deltas(result.batter_deltas)
            batter_dual.career.increment_pa()
            pitcher_dual.career.apply_deltas(result.pitcher_deltas)
            pitcher_dual.career.increment_bfp()
            # Career event counts
            for b_idx in range(5):
                if result.batter_deltas[b_idx] != 0:
                    batter_dual.career.event_counts[b_idx] += 1
            for p_idx in range(4):
                if result.pitcher_deltas[p_idx] != 0:
                    pitcher_dual.career.event_counts[p_idx] += 1

            # Record OHLC updates (after PA)
            for b_idx, dim_name in enumerate(BATTER_DIM_NAMES):
                self._update_ohlc(batter_id, dim_name, float(batter.elo_dimensions[b_idx]))
            for p_idx, dim_name in enumerate(PITCHER_DIM_NAMES):
                self._update_ohlc(pitcher_id, dim_name, float(pitcher.elo_dimensions[p_idx]))

            # PA detail records (per affected dimension)
            pa_id = int(row['pa_id'])
            for b_idx, dim_name in enumerate(BATTER_DIM_NAMES):
                if result.batter_deltas[b_idx] != 0:
                    self.talent_pa_details.append({
                        'pa_id': pa_id,
                        'player_id': batter_id,
                        'player_role': 'batter',
                        'talent_type': dim_name,
                        'elo_before': float(batter_before[b_idx]),
                        'elo_after': float(batter.elo_dimensions[b_idx]),
                        'delta': float(result.batter_deltas[b_idx]),
                    })
            for p_idx, dim_name in enumerate(PITCHER_DIM_NAMES):
                if result.pitcher_deltas[p_idx] != 0:
                    self.talent_pa_details.append({
                        'pa_id': pa_id,
                        'player_id': pitcher_id,
                        'player_role': 'pitcher',
                        'talent_type': dim_name,
                        'elo_before': float(pitcher_before[p_idx]),
                        'elo_after': float(pitcher.elo_dimensions[p_idx]),
                        'delta': float(result.pitcher_deltas[p_idx]),
                    })

            if (idx + 1) % 50000 == 0:
                logger.info(f"  Talent: Processed {idx + 1:,} / {total:,} PAs")

        # Finalize last day
        if self._current_date is not None:
            self._finalize_day(self._current_date)

        logger.info(
            f"  Talent: Completed {total:,} PAs, "
            f"{len(self.talent_pa_details):,} detail records, "
            f"{len(self.talent_daily_ohlc):,} OHLC records"
        )

    def get_talent_player_records(self, active_only: bool = False) -> list[dict]:
        """Generate talent_player_current table records."""
        records = []
        for pid, dual in self.state_mgr.all_batters.items():
            if active_only and pid not in self._active_player_ids:
                continue
            for b_idx, dim_name in enumerate(BATTER_DIM_NAMES):
                records.append({
                    'player_id': pid,
                    'player_role': 'batter',
                    'talent_type': dim_name,
                    'season_elo': float(dual.season.elo_dimensions[b_idx]),
                    'career_elo': float(dual.career.elo_dimensions[b_idx]),
                    'event_count': int(dual.season.event_counts[b_idx]),
                    'pa_count': dual.season.pa_count,
                })
        for pid, dual in self.state_mgr.all_pitchers.items():
            if active_only and pid not in self._active_player_ids:
                continue
            for p_idx, dim_name in enumerate(PITCHER_DIM_NAMES):
                records.append({
                    'player_id': pid,
                    'player_role': 'pitcher',
                    'talent_type': dim_name,
                    'season_elo': float(dual.season.elo_dimensions[p_idx]),
                    'career_elo': float(dual.career.elo_dimensions[p_idx]),
                    'event_count': int(dual.season.event_counts[p_idx]),
                    'pa_count': dual.season.bfp_count,
                })
        return records
