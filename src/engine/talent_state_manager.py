"""Talent State Manager — Season/Career dual tracking for 9D talent.

Season reset uses FiveThirtyEight-style formula:
  new_elo = proj_weight * projection_elo + prior_weight * regressed_final_elo
  where regressed_final_elo = final_elo + regression * (1500 - final_elo)
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.engine.multi_elo_types import BatterTalentState, PitcherTalentState, DEFAULT_ELO

# FiveThirtyEight-style reset weights
PROJECTION_WEIGHT = 0.67
PRIOR_SEASON_WEIGHT = 0.33
PRIOR_SEASON_REGRESSION = 1 / 3  # regress 1/3 toward mean


@dataclass
class DualBatterState:
    """Batter dual state: Season (resets yearly) + Career (cumulative)."""
    player_id: int
    season: BatterTalentState = field(default=None)
    career: BatterTalentState = field(default=None)

    def __post_init__(self):
        if self.season is None:
            self.season = BatterTalentState(player_id=self.player_id)
        if self.career is None:
            self.career = BatterTalentState(player_id=self.player_id)

    def apply_deltas(self, deltas: np.ndarray) -> None:
        self.season.apply_deltas(deltas)
        self.career.apply_deltas(deltas)
        self.season.increment_pa()
        self.career.increment_pa()

    def reset_season(self, projected_elo: Optional[np.ndarray] = None) -> None:
        """Reset season ELO using FiveThirtyEight formula.

        If projected_elo is provided:
          new = 0.67 * projected + 0.33 * (final + 1/3 * (1500 - final))
        Otherwise: reset to 1500 (fallback for players without projections).
        """
        if projected_elo is not None:
            final = self.season.elo_dimensions.copy()
            regressed = final + PRIOR_SEASON_REGRESSION * (DEFAULT_ELO - final)
            new_elo = PROJECTION_WEIGHT * projected_elo + PRIOR_SEASON_WEIGHT * regressed
            new_state = BatterTalentState(player_id=self.player_id)
            new_state.elo_dimensions = new_elo
            self.season = new_state
        else:
            self.season = BatterTalentState(player_id=self.player_id)


@dataclass
class DualPitcherState:
    """Pitcher dual state: Season (resets yearly) + Career (cumulative)."""
    player_id: int
    season: PitcherTalentState = field(default=None)
    career: PitcherTalentState = field(default=None)

    def __post_init__(self):
        if self.season is None:
            self.season = PitcherTalentState(player_id=self.player_id)
        if self.career is None:
            self.career = PitcherTalentState(player_id=self.player_id)

    def apply_deltas(self, deltas: np.ndarray) -> None:
        self.season.apply_deltas(deltas)
        self.career.apply_deltas(deltas)
        self.season.increment_bfp()
        self.career.increment_bfp()

    def reset_season(self, projected_elo: Optional[np.ndarray] = None) -> None:
        """Reset season ELO using FiveThirtyEight formula."""
        if projected_elo is not None:
            final = self.season.elo_dimensions.copy()
            regressed = final + PRIOR_SEASON_REGRESSION * (DEFAULT_ELO - final)
            new_elo = PROJECTION_WEIGHT * projected_elo + PRIOR_SEASON_WEIGHT * regressed
            new_state = PitcherTalentState(player_id=self.player_id)
            new_state.elo_dimensions = new_elo
            self.season = new_state
        else:
            self.season = PitcherTalentState(player_id=self.player_id)


class TalentStateManager:
    """Manages all batter and pitcher talent states."""

    def __init__(
        self,
        initial_batters: dict[int, DualBatterState] | None = None,
        initial_pitchers: dict[int, DualPitcherState] | None = None,
    ):
        self._batters: dict[int, DualBatterState] = dict(initial_batters) if initial_batters else {}
        self._pitchers: dict[int, DualPitcherState] = dict(initial_pitchers) if initial_pitchers else {}
        self._current_season: Optional[int] = None

    def get_or_create_batter(self, player_id: int) -> DualBatterState:
        if player_id not in self._batters:
            self._batters[player_id] = DualBatterState(player_id=player_id)
        return self._batters[player_id]

    def get_or_create_pitcher(self, player_id: int) -> DualPitcherState:
        if player_id not in self._pitchers:
            self._pitchers[player_id] = DualPitcherState(player_id=player_id)
        return self._pitchers[player_id]

    def reset_season(
        self,
        new_season: int,
        batter_projections: Optional[dict[int, np.ndarray]] = None,
        pitcher_projections: Optional[dict[int, np.ndarray]] = None,
    ) -> None:
        """Reset all players for new season with optional projection-based ELO."""
        bat_proj = batter_projections or {}
        pit_proj = pitcher_projections or {}
        for pid, b in self._batters.items():
            b.reset_season(bat_proj.get(pid))
        for pid, p in self._pitchers.items():
            p.reset_season(pit_proj.get(pid))
        self._current_season = new_season

    @property
    def all_batters(self) -> dict[int, DualBatterState]:
        return self._batters

    @property
    def all_pitchers(self) -> dict[int, DualPitcherState]:
        return self._pitchers

    @property
    def current_season(self) -> Optional[int]:
        return self._current_season
