"""
Park Factor — 구장별 Run Value 보정

Park factor로 venue scoring environment를 보정.
adjustment = (park_factor - 1.0) × ADJUSTMENT_SCALE
adjusted_rv = actual_rv - adjustment

Port from: balltology-elo/src/park_factor.py
"""

import os

import pandas as pd

from src.engine.elo_config import ADJUSTMENT_SCALE


DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'mlb_park_factors.csv'
)


class ParkFactor:
    """구장별 Park Factor 보정."""

    def __init__(self, csv_path: str = None):
        csv_path = csv_path or DEFAULT_CSV_PATH
        df = pd.read_csv(csv_path)
        self._park_factors: dict[str, float] = dict(zip(df['home_team'], df['park_factor']))

    def get_park_factor(self, home_team: str) -> float:
        """홈팀의 Park Factor 반환. 없으면 1.0 (neutral)."""
        return self._park_factors.get(home_team, 1.0)

    def get_adjustment(self, home_team: str) -> float:
        """Park factor RV 조정값 반환.

        adjustment = (park_factor - 1.0) × ADJUSTMENT_SCALE
        """
        pf = self.get_park_factor(home_team)
        return (pf - 1.0) * ADJUSTMENT_SCALE

    def adjust_rv(self, actual_rv: float, home_team: str) -> float:
        """Run Value를 park factor로 보정.

        adjusted_rv = actual_rv - adjustment
        (높은 PF 구장에서는 RV를 하향 보정)
        """
        return actual_rv - self.get_adjustment(home_team)
