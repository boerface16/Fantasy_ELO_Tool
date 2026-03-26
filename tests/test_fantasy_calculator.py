"""Tests for fantasy_calculator — matchup probabilities → ESPN fantasy points."""

import pytest
from src.fantasy.fantasy_calculator import (
    estimate_batter_points,
    estimate_pitcher_points,
    load_scoring_config,
)


@pytest.fixture
def scoring():
    return load_scoring_config()


@pytest.fixture
def avg_probs():
    """League-average PA probabilities."""
    return {
        "BB": 0.0949,
        "K": 0.2218,
        "OUT": 0.4645,
        "1B": 0.1423,
        "2B": 0.0424,
        "3B": 0.0034,
        "HR": 0.0308,
    }


class TestBatterPoints:

    def test_positive_expected_points(self, scoring, avg_probs):
        """Average batter should have positive expected points per PA."""
        pts = estimate_batter_points(avg_probs, scoring)
        assert pts > 0

    def test_high_power_more_points(self, scoring):
        """Batter with high HR probability should score more."""
        avg = {"BB": 0.09, "K": 0.22, "OUT": 0.40, "1B": 0.14, "2B": 0.04, "3B": 0.003, "HR": 0.10}
        low = {"BB": 0.09, "K": 0.22, "OUT": 0.50, "1B": 0.14, "2B": 0.04, "3B": 0.003, "HR": 0.01}
        assert estimate_batter_points(avg, scoring) > estimate_batter_points(low, scoring)

    def test_strikeout_penalty(self, scoring):
        """More strikeouts should reduce points."""
        low_k = {"BB": 0.10, "K": 0.10, "OUT": 0.50, "1B": 0.15, "2B": 0.05, "3B": 0.005, "HR": 0.04}
        high_k = {"BB": 0.10, "K": 0.35, "OUT": 0.30, "1B": 0.10, "2B": 0.05, "3B": 0.005, "HR": 0.04}
        assert estimate_batter_points(low_k, scoring) > estimate_batter_points(high_k, scoring)

    def test_walk_gives_points(self, scoring):
        """Walks should add points (BB = +1)."""
        no_bb = {"BB": 0.00, "K": 0.22, "OUT": 0.50, "1B": 0.14, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        hi_bb = {"BB": 0.15, "K": 0.22, "OUT": 0.35, "1B": 0.14, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        assert estimate_batter_points(hi_bb, scoring) > estimate_batter_points(no_bb, scoring)

    def test_returns_float(self, scoring, avg_probs):
        pts = estimate_batter_points(avg_probs, scoring)
        assert isinstance(pts, float)


class TestPitcherPoints:

    def test_positive_for_dominant_pitcher(self, scoring):
        """High-K, low-hit pitcher should score well."""
        probs = {"BB": 0.05, "K": 0.30, "OUT": 0.50, "1B": 0.08, "2B": 0.03, "3B": 0.002, "HR": 0.02}
        pts = estimate_pitcher_points(probs, scoring, innings=6.0)
        assert pts > 0

    def test_more_innings_more_points(self, scoring):
        """More innings pitched should generally increase points."""
        probs = {"BB": 0.08, "K": 0.25, "OUT": 0.45, "1B": 0.12, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        pts_5 = estimate_pitcher_points(probs, scoring, innings=5.0)
        pts_7 = estimate_pitcher_points(probs, scoring, innings=7.0)
        assert pts_7 > pts_5

    def test_high_bb_reduces_points(self, scoring):
        """High walk rate should reduce pitcher points."""
        low_bb = {"BB": 0.05, "K": 0.25, "OUT": 0.48, "1B": 0.12, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        hi_bb = {"BB": 0.15, "K": 0.25, "OUT": 0.38, "1B": 0.12, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        assert estimate_pitcher_points(low_bb, scoring) > estimate_pitcher_points(hi_bb, scoring)

    def test_returns_float(self, scoring):
        probs = {"BB": 0.08, "K": 0.25, "OUT": 0.45, "1B": 0.12, "2B": 0.04, "3B": 0.003, "HR": 0.03}
        pts = estimate_pitcher_points(probs, scoring)
        assert isinstance(pts, float)


class TestScoringConfig:

    def test_load_config(self, scoring):
        assert "batter" in scoring
        assert "pitcher" in scoring

    def test_batter_scoring_keys(self, scoring):
        assert scoring["batter"]["TB"] == 1
        assert scoring["batter"]["SO"] == -1
        assert scoring["batter"]["BB"] == 1

    def test_pitcher_scoring_keys(self, scoring):
        assert scoring["pitcher"]["IP"] == 3
        assert scoring["pitcher"]["K"] == 1
        assert scoring["pitcher"]["ER"] == -2
