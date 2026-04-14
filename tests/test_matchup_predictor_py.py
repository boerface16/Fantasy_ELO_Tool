"""Tests for Python port of matchupPredictor.ts (V2.1 3-stage decision tree).

Cross-validates against TypeScript constants and known outputs.
"""

import math
import pytest
from src.fantasy.matchup_predictor import (
    predict_plate_appearance,
    elo_to_zscore,
    zscore_to_probability,
    stage1_softmax,
    MLB_ELO_DISTRIBUTION,
    MLB_LEAGUE_AVERAGES,
    WOBA_WEIGHTS,
    LEAGUE_AVG_WOBA,
)


# --- Constants match TypeScript ---

def test_elo_distribution_keys():
    expected = {
        "BATTER_CONTACT", "BATTER_POWER", "BATTER_DISCIPLINE", "BATTER_SPEED",
        "PITCHER_STUFF", "PITCHER_BIP_SUPPRESSION", "PITCHER_COMMAND",
        "PITCHER_CLUTCH",
    }
    assert set(MLB_ELO_DISTRIBUTION.keys()) == expected


def test_league_averages_sum_to_one():
    la = MLB_LEAGUE_AVERAGES
    assert abs(la["bb_rate"] + la["k_rate"] + la["bip_rate"] - 1.0) < 1e-4


def test_xbh_ratios_sum_to_one():
    la = MLB_LEAGUE_AVERAGES
    assert abs(la["2b_ratio"] + la["3b_ratio"] + la["hr_ratio"] - 1.0) < 1e-4


def test_woba_weights_match_ts():
    assert WOBA_WEIGHTS["BB"] == 0.69
    assert WOBA_WEIGHTS["HR"] == 2.00
    assert WOBA_WEIGHTS["K"] == 0.0
    assert WOBA_WEIGHTS["1B"] == 0.88


# --- elo_to_zscore ---

def test_elo_to_zscore_at_mean():
    mean = MLB_ELO_DISTRIBUTION["BATTER_CONTACT"]["mean"]
    assert elo_to_zscore(mean, "BATTER_CONTACT") == pytest.approx(0.0, abs=1e-6)


def test_elo_to_zscore_one_std_above():
    dist = MLB_ELO_DISTRIBUTION["BATTER_POWER"]
    assert elo_to_zscore(dist["mean"] + dist["std"], "BATTER_POWER") == pytest.approx(1.0, abs=1e-6)


def test_elo_to_zscore_unknown_type():
    assert elo_to_zscore(1500, "UNKNOWN") == 0.0


# --- zscore_to_probability ---

def test_zscore_to_prob_zero_diff():
    """Zero z-diff should return base rate."""
    assert zscore_to_probability(0.0, 3.5, 0.25) == pytest.approx(0.25, abs=1e-6)


def test_zscore_to_prob_positive():
    """Positive z-diff should increase probability above base rate."""
    assert zscore_to_probability(1.0, 3.5, 0.25) > 0.25


def test_zscore_to_prob_negative():
    """Negative z-diff should decrease probability below base rate."""
    assert zscore_to_probability(-1.0, 3.5, 0.25) < 0.25


# --- stage1_softmax ---

def test_stage1_softmax_sums_to_one():
    result = stage1_softmax(0.0, 0.0)
    assert abs(result["pBB"] + result["pK"] + result["pBIP"] - 1.0) < 1e-6


def test_stage1_softmax_at_zero():
    """Zero z-diffs should return league averages."""
    result = stage1_softmax(0.0, 0.0)
    la = MLB_LEAGUE_AVERAGES
    assert result["pBB"] == pytest.approx(la["bb_rate"], abs=1e-4)
    assert result["pK"] == pytest.approx(la["k_rate"], abs=1e-4)
    assert result["pBIP"] == pytest.approx(la["bip_rate"], abs=1e-4)


def test_stage1_high_discipline_more_bb():
    """Higher discipline-command diff → more walks."""
    base = stage1_softmax(0.0, 0.0)
    high_disc = stage1_softmax(2.0, 0.0)
    assert high_disc["pBB"] > base["pBB"]


def test_stage1_high_stuff_more_k():
    """Higher stuff-contact diff → more strikeouts."""
    base = stage1_softmax(0.0, 0.0)
    high_stuff = stage1_softmax(0.0, 2.0)
    assert high_stuff["pK"] > base["pK"]


# --- predict_plate_appearance ---

class TestPredictPA:
    """Test the full prediction pipeline."""

    @pytest.fixture
    def avg_batter(self):
        return {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}

    @pytest.fixture
    def avg_pitcher(self):
        return {"stuff": 1587.3, "bip_suppression": 1513.3, "command": 1681.1}

    @pytest.fixture
    def elite_batter(self):
        return {"contact": 1550.0, "power": 1600.0, "discipline": 1900.0}

    @pytest.fixture
    def elite_pitcher(self):
        return {"stuff": 1650.0, "bip_suppression": 1540.0, "command": 1850.0}

    def test_probabilities_sum_to_one(self, avg_batter, avg_pitcher):
        pred = predict_plate_appearance(avg_batter, avg_pitcher)
        total = sum(pred["probabilities"].values())
        assert abs(total - 1.0) < 1e-6

    def test_avg_vs_avg_matches_league_rates(self, avg_batter, avg_pitcher):
        """Average batter vs average pitcher should produce league-average rates.

        LR-3: BB is now split into BB + HBP; check combined free-base rate vs la["bb_rate"].
        """
        pred = predict_plate_appearance(avg_batter, avg_pitcher)
        la = MLB_LEAGUE_AVERAGES
        probs = pred["probabilities"]
        assert probs["BB"] + probs.get("HBP", 0) == pytest.approx(la["bb_rate"], abs=0.005)
        assert probs["K"] == pytest.approx(la["k_rate"], abs=0.005)

    def test_avg_vs_avg_woba_matches_league(self, avg_batter, avg_pitcher):
        pred = predict_plate_appearance(avg_batter, avg_pitcher)
        assert pred["expected_woba"] == pytest.approx(LEAGUE_AVG_WOBA, abs=0.005)

    def test_elite_batter_higher_woba(self, elite_batter, avg_pitcher, avg_batter):
        elite = predict_plate_appearance(elite_batter, avg_pitcher)
        avg = predict_plate_appearance(avg_batter, avg_pitcher)
        assert elite["expected_woba"] > avg["expected_woba"]

    def test_elite_pitcher_lower_woba(self, avg_batter, elite_pitcher, avg_pitcher):
        elite = predict_plate_appearance(avg_batter, elite_pitcher)
        avg = predict_plate_appearance(avg_batter, avg_pitcher)
        assert elite["expected_woba"] < avg["expected_woba"]

    def test_zdiffs_present(self, avg_batter, avg_pitcher):
        pred = predict_plate_appearance(avg_batter, avg_pitcher)
        assert "z_diffs" in pred
        for key in ("z_disc_cmd", "z_stuff_contact", "z_contact_bip", "z_stuff_power"):
            assert key in pred["z_diffs"]

    def test_stages_present(self, avg_batter, avg_pitcher):
        pred = predict_plate_appearance(avg_batter, avg_pitcher)
        assert "stages" in pred
        assert "stage1" in pred["stages"]
        assert "stage2" in pred["stages"]
        assert "stage3" in pred["stages"]

    def test_all_probs_positive(self, elite_batter, elite_pitcher):
        pred = predict_plate_appearance(elite_batter, elite_pitcher)
        for key, val in pred["probabilities"].items():
            assert val > 0, f"{key} probability should be positive"

    def test_cross_validate_known_matchup(self):
        """Cross-validate against manually computed TypeScript output.

        Batter: contact=1540, power=1530, discipline=1800
        Pitcher: stuff=1640, bip_suppression=1520, command=1750
        """
        batter = {"contact": 1540.0, "power": 1530.0, "discipline": 1800.0}
        pitcher = {"stuff": 1640.0, "bip_suppression": 1520.0, "command": 1750.0}
        pred = predict_plate_appearance(batter, pitcher)

        # Stage 1 z-diffs
        z_disc = (1800.0 - 1700.3) / 139.0  # 0.7176
        z_cmd = (1750.0 - 1681.1) / 126.5   # 0.5447
        z_disc_cmd = z_disc - z_cmd           # 0.1729

        z_stuff = (1640.0 - 1587.3) / 56.6  # 0.9311
        z_contact = (1540.0 - 1504.5) / 33.9  # 1.0472
        z_stuff_contact = z_stuff - z_contact  # -0.1161

        assert pred["z_diffs"]["z_disc_cmd"] == pytest.approx(z_disc_cmd, abs=0.01)
        assert pred["z_diffs"]["z_stuff_contact"] == pytest.approx(z_stuff_contact, abs=0.01)

        # Probabilities should sum to 1
        assert abs(sum(pred["probabilities"].values()) - 1.0) < 1e-6


# --- LEAGUE_AVG_WOBA ---

def test_league_avg_woba_reasonable():
    """League average wOBA should be in typical MLB range."""
    assert 0.28 < LEAGUE_AVG_WOBA < 0.35
