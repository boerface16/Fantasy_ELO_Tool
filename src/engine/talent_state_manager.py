"""Talent State Manager — Season/Career dual tracking for 9D talent."""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.engine.multi_elo_types import BatterTalentState, PitcherTalentState, DEFAULT_ELO


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

    def reset_season(self) -> None:
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

    def reset_season(self) -> None:
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

    def reset_season(self, new_season: int) -> None:
        for b in self._batters.values():
            b.reset_season()
        for p in self._pitchers.values():
            p.reset_season()
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
