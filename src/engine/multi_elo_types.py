"""Multi-Dimensional ELO Types (9D Talent System).

Batter 5D: Contact, Power, Discipline, Speed, Clutch
Pitcher 4D: Stuff, BIP_Suppression, Command, Clutch
"""
from dataclasses import dataclass, field

import numpy as np

# === Constants ===

DEFAULT_ELO = 1500.0
ELO_MIN = 500.0
ELO_MAX = 3000.0
MIN_RELIABILITY = 0.3

BATTER_DIM_COUNT = 5
BATTER_DIM_NAMES = ["contact", "power", "discipline", "speed", "clutch"]

PITCHER_DIM_COUNT = 4
PITCHER_DIM_NAMES = ["stuff", "bip_suppression", "command", "clutch"]

BATTER_DEFAULT_WEIGHTS = np.array([0.20, 0.20, 0.20, 0.20, 0.20])

PITCHER_ROLE_WEIGHTS = {
    "starter": np.array([0.25, 0.20, 0.40, 0.15]),
    "reliever": np.array([0.35, 0.20, 0.30, 0.15]),
    "closer": np.array([0.35, 0.25, 0.25, 0.15]),
}


@dataclass
class BatterTalentState:
    """Batter 5D talent ELO state."""
    player_id: int
    elo_dimensions: np.ndarray = field(default_factory=lambda: np.full(BATTER_DIM_COUNT, DEFAULT_ELO))
    event_counts: np.ndarray = field(default_factory=lambda: np.zeros(BATTER_DIM_COUNT))
    pa_count: int = 0

    CONTACT = 0
    POWER = 1
    DISCIPLINE = 2
    SPEED = 3
    CLUTCH = 4

    @property
    def composite_elo(self) -> float:
        return float(np.dot(self.elo_dimensions, BATTER_DEFAULT_WEIGHTS))

    def apply_deltas(self, deltas: np.ndarray) -> None:
        self.elo_dimensions = np.clip(self.elo_dimensions + deltas, ELO_MIN, ELO_MAX)

    def increment_pa(self) -> None:
        self.pa_count += 1


@dataclass
class PitcherTalentState:
    """Pitcher 4D talent ELO state."""
    player_id: int
    elo_dimensions: np.ndarray = field(default_factory=lambda: np.full(PITCHER_DIM_COUNT, DEFAULT_ELO))
    event_counts: np.ndarray = field(default_factory=lambda: np.zeros(PITCHER_DIM_COUNT))
    bfp_count: int = 0
    role: str = "starter"

    STUFF = 0
    BIP_SUPPRESSION = 1
    COMMAND = 2
    CLUTCH = 3

    @property
    def composite_elo(self) -> float:
        weights = PITCHER_ROLE_WEIGHTS.get(self.role, PITCHER_ROLE_WEIGHTS["starter"])
        return float(np.dot(self.elo_dimensions, weights))

    def apply_deltas(self, deltas: np.ndarray) -> None:
        self.elo_dimensions = np.clip(self.elo_dimensions + deltas, ELO_MIN, ELO_MAX)

    def increment_bfp(self) -> None:
        self.bfp_count += 1
