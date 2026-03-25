"""Multi-Dimensional ELO Engine (9D Talent System).

Batter 5D: Contact, Power, Discipline, Speed, Clutch
Pitcher 4D: Stuff, BIP_Suppression, Command, Clutch

Binary matchup model: delta = K * scale * |weight| * (actual - expected) * reliability
DIPS-based asymmetric pitcher weights (V2).
"""
from dataclasses import dataclass

import numpy as np

from src.engine.multi_elo_config import MultiEloConfig
from src.engine.multi_elo_types import (
    BatterTalentState,
    PitcherTalentState,
    BATTER_DIM_NAMES,
    PITCHER_DIM_NAMES,
    MIN_RELIABILITY,
)


@dataclass
class TalentUpdateResult:
    """Per-PA talent ELO update result."""
    batter_deltas: np.ndarray   # 5D
    pitcher_deltas: np.ndarray  # 4D
    batter_elo_after: np.ndarray
    pitcher_elo_after: np.ndarray
    event_type: str
    is_clutch: bool


class MultiEloEngine:
    """9-Dimensional Talent ELO Engine."""

    BATTER_TO_PITCHER = {
        "contact": "stuff",
        "power": "bip_suppression",
        "discipline": "command",
        "speed": None,
        "clutch": "clutch",
    }

    PITCHER_TO_BATTER = {
        "stuff": "contact",
        "bip_suppression": "contact",
        "command": "discipline",
        "clutch": "clutch",
    }

    def __init__(self, config: MultiEloConfig | None = None):
        self.config = config or MultiEloConfig()

    def calculate_expected_score(
        self, player_elo: float, opponent_elo: float, divisor: float = 400.0
    ) -> float:
        """Standard ELO expected score: E = 1 / (1 + 10^((opp - player) / divisor))."""
        return 1.0 / (1.0 + 10.0 ** ((opponent_elo - player_elo) / divisor))

    def calculate_reliability(
        self, event_count: int, dimension: str, is_pitcher: bool = False
    ) -> float:
        """Reliability ramp: MIN_RELIABILITY + (1 - MIN_RELIABILITY) * (count / threshold).

        Returns 1.0 when event_count >= threshold.
        """
        threshold = self.config.get_reliability_threshold(dimension, is_pitcher)
        if event_count >= threshold:
            return 1.0
        return MIN_RELIABILITY + (1 - MIN_RELIABILITY) * (event_count / threshold)

    def get_clutch_multiplier(self, leverage_index: float) -> float:
        """Clutch multiplier: 0 if LI <= 1.0, else min(max_mult, LI / 2)."""
        if leverage_index <= 1.0:
            return 0.0
        max_mult = self.config.max_clutch_multiplier
        return min(max_mult, leverage_index / 2.0)

    def process_plate_appearance(
        self,
        batter: BatterTalentState,
        pitcher: PitcherTalentState,
        result_type: str,
        leverage_index: float = 1.0,
        is_risp: bool = False,
    ) -> TalentUpdateResult:
        """Process a single plate appearance through the 9D engine.

        Args:
            batter: Batter talent state (mutated in place).
            pitcher: Pitcher talent state (mutated in place).
            result_type: PA outcome (e.g. "HR", "StrikeOut", "BB", "Single").
            leverage_index: Leverage index for clutch calculation (default 1.0).
            is_risp: Whether runners are in scoring position.

        Returns:
            TalentUpdateResult with per-dimension deltas and updated ELO arrays.
        """
        batter_weights = self.config.get_event_weights(result_type)
        pitcher_weights = self.config.get_pitcher_event_weights(result_type)
        clutch_mult = self.get_clutch_multiplier(leverage_index)
        is_clutch = leverage_index > self.config.leverage_threshold or is_risp

        # RISP triggers minimum clutch activation
        if is_risp and clutch_mult == 0.0:
            clutch_mult = 0.5

        # GIDP clutch multiplier
        if result_type == "GIDP":
            gidp_mult = batter_weights.get("clutch_multiplier", 1.0)
            clutch_mult *= gidp_mult

        batter_deltas = np.zeros(5)
        pitcher_deltas = np.zeros(4)

        # === Batter loop (5D) ===
        for b_idx, b_dim in enumerate(BATTER_DIM_NAMES):
            weight = batter_weights.get(b_dim, 0.0)

            if b_dim == "clutch":
                base_weight = batter_weights.get("clutch_base", 0.0)
                if clutch_mult > 0:
                    weight = base_weight * (1.0 + clutch_mult)
                else:
                    weight = base_weight * 0.5

            if weight == 0.0:
                continue

            p_dim = self.BATTER_TO_PITCHER.get(b_dim)
            k = self.config.get_batter_k_factor(b_dim)
            scale = self.config.get_batter_scale(b_dim)
            reliability = self.calculate_reliability(
                int(batter.event_counts[b_idx]), b_dim
            )

            if p_dim is None:
                # Speed: no pitcher matchup, use 0.5 baseline
                actual = 1.0 if weight > 0 else 0.0
                expected = 0.5
            else:
                p_idx = PITCHER_DIM_NAMES.index(p_dim)
                b_divisor = self.config.get_expected_divisor(b_dim, is_pitcher=False)
                p_divisor = self.config.get_expected_divisor(p_dim, is_pitcher=True)
                divisor = (b_divisor + p_divisor) / 2

                expected = self.calculate_expected_score(
                    batter.elo_dimensions[b_idx],
                    pitcher.elo_dimensions[p_idx],
                    divisor=divisor,
                )
                actual = 1.0 if weight > 0 else 0.0

            delta = k * scale * abs(weight) * (actual - expected) * reliability
            batter_deltas[b_idx] = delta

        # === Pitcher loop (4D, V2: independent asymmetric weights) ===
        for p_idx, p_dim in enumerate(PITCHER_DIM_NAMES):
            weight = pitcher_weights.get(p_dim, 0.0)

            if p_dim == "clutch":
                base_weight = pitcher_weights.get("clutch_base", 0.0)
                if clutch_mult > 0:
                    weight = base_weight * (1.0 + clutch_mult)
                else:
                    weight = base_weight * 0.5

            if weight == 0.0:
                continue

            b_dim = self.PITCHER_TO_BATTER.get(p_dim)
            b_idx = BATTER_DIM_NAMES.index(b_dim) if b_dim else None

            k = self.config.get_pitcher_k_factor(p_dim)
            scale = self.config.get_pitcher_scale(p_dim)
            reliability = self.calculate_reliability(
                int(pitcher.event_counts[p_idx]), p_dim, is_pitcher=True
            )

            if b_idx is not None:
                b_divisor = self.config.get_expected_divisor(b_dim, is_pitcher=False)
                p_divisor = self.config.get_expected_divisor(p_dim, is_pitcher=True)
                divisor = (b_divisor + p_divisor) / 2
                expected = self.calculate_expected_score(
                    pitcher.elo_dimensions[p_idx],
                    batter.elo_dimensions[b_idx],
                    divisor=divisor,
                )
            else:
                expected = 0.5

            actual = 1.0 if weight > 0 else 0.0
            delta = k * scale * abs(weight) * (actual - expected) * reliability
            pitcher_deltas[p_idx] += delta

        # Update states
        batter.apply_deltas(batter_deltas)
        pitcher.apply_deltas(pitcher_deltas)

        # Increment event counts for dimensions with non-zero deltas
        for b_idx in range(5):
            if batter_deltas[b_idx] != 0:
                batter.event_counts[b_idx] += 1
        for p_idx in range(4):
            if pitcher_deltas[p_idx] != 0:
                pitcher.event_counts[p_idx] += 1

        batter.increment_pa()
        pitcher.increment_bfp()

        return TalentUpdateResult(
            batter_deltas=batter_deltas,
            pitcher_deltas=pitcher_deltas,
            batter_elo_after=batter.elo_dimensions.copy(),
            pitcher_elo_after=pitcher.elo_dimensions.copy(),
            event_type=result_type,
            is_clutch=is_clutch,
        )
