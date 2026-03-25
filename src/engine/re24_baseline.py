"""
RE24 Baseline — State별 평균 Run Value

Base-out state(0~23)별 기대 delta_run_exp를 제공.
State normalization: rv_diff = actual_rv - expected_rv[state]

Port from: balltology-elo/src/re24_baseline.py
"""

import os

import pandas as pd


DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'mlb_re24_baseline.csv'
)


class RE24Baseline:
    """State별 기대 Run Value 제공."""

    def __init__(self, csv_path: str = None):
        csv_path = csv_path or DEFAULT_CSV_PATH
        df = pd.read_csv(csv_path)
        self._mean_rv: dict[int, float] = dict(zip(df['state_id'], df['mean_rv']))

    def get_expected_rv(self, state: int) -> float:
        """주어진 base-out state의 기대 Run Value 반환.

        Args:
            state: 0~23 (base-out state encoding)

        Returns:
            해당 state의 평균 delta_run_exp. 없으면 0.0.
        """
        return self._mean_rv.get(state, 0.0)
