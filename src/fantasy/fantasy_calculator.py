"""Convert matchup probabilities to ESPN H2H fantasy points.

Uses PA outcome probabilities from matchup_predictor to estimate
expected fantasy points per PA (batters) or per start (pitchers).
"""

import os
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "espn_scoring.yaml")

# Average batters faced per inning for estimating pitcher PA count
AVG_BF_PER_INNING = 4.3


def load_scoring_config() -> dict:
    """Load ESPN scoring weights from config/espn_scoring.yaml."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def estimate_batter_points(probs: dict[str, float], scoring: dict, pas: int = 1) -> float:
    """Estimate expected fantasy points for a batter.

    Args:
        probs: PA outcome probabilities (BB, K, OUT, 1B, 2B, 3B, HR)
        scoring: scoring config dict with 'batter' key
        pas: number of plate appearances (default 1 = per-PA rate)

    Returns:
        expected fantasy points
    """
    rules = scoring["batter"]

    # Total bases: 1B=1, 2B=2, 3B=3, HR=4
    e_tb = (probs.get("1B", 0) * 1
            + probs.get("2B", 0) * 2
            + probs.get("3B", 0) * 3
            + probs.get("HR", 0) * 4)

    # BB
    e_bb = probs.get("BB", 0)

    # Strikeouts (penalty)
    e_so = probs.get("K", 0)

    # R and RBI are harder to estimate from PA probs alone.
    # Use expected total bases as a proxy: ~40% of TB become runs, ~45% become RBI
    # (rough MLB averages from seasonal correlations)
    e_runs = e_tb * 0.40
    e_rbi = e_tb * 0.45

    # SB: estimate ~2% of times on base (1B + BB)
    e_sb = (probs.get("1B", 0) + probs.get("BB", 0)) * 0.02

    pts_per_pa = (
        e_tb * rules.get("TB", 1)
        + e_runs * rules.get("R", 1)
        + e_rbi * rules.get("RBI", 1)
        + e_bb * rules.get("BB", 1)
        + e_sb * rules.get("SB", 1)
        + e_so * rules.get("SO", -1)
    )

    return float(pts_per_pa * pas)


def estimate_pitcher_points(probs: dict[str, float], scoring: dict,
                            innings: float = 6.0) -> float:
    """Estimate expected fantasy points for a pitcher start.

    Args:
        probs: PA outcome probabilities (from batter's perspective — inverted)
        scoring: scoring config dict with 'pitcher' key
        innings: expected innings pitched (default 6.0 for a starter)

    Returns:
        expected fantasy points for the start
    """
    rules = scoring["pitcher"]

    # Estimate total batters faced
    bf = innings * AVG_BF_PER_INNING

    # Per-BF rates (from batter perspective → invert for pitcher value)
    k_per_bf = probs.get("K", 0.22)
    bb_per_bf = probs.get("BB", 0.09)
    hit_per_bf = (probs.get("1B", 0) + probs.get("2B", 0)
                  + probs.get("3B", 0) + probs.get("HR", 0))

    # Expected counts
    e_k = k_per_bf * bf
    e_bb = bb_per_bf * bf
    e_hits = hit_per_bf * bf

    # ER estimate: ~30% of baserunners score (rough MLB average)
    baserunners = e_hits + e_bb
    e_er = baserunners * 0.30

    pts = (
        innings * rules.get("IP", 3)
        + e_k * rules.get("K", 1)
        + e_hits * rules.get("H", -1)
        + e_er * rules.get("ER", -2)
        + e_bb * rules.get("BB", -1)
    )

    return float(pts)
