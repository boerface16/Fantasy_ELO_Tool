"""Convert matchup probabilities to ESPN H2H fantasy points.

Uses PA outcome probabilities from matchup_predictor to estimate
expected fantasy points per PA (batters) or per start/appearance (pitchers).
"""

import os
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "espn_scoring.yaml")

# Average batters faced per inning for estimating pitcher PA count
AVG_BF_PER_INNING = 4.3

# Speed ELO distribution (approximated — re-calibrate once speed ELO accumulates data)
SPEED_ELO_MEAN = 1500.0
SPEED_ELO_STD = 50.0

# MLB average SBs allowed per pitcher per team game (rough league average)
MLB_AVG_SB_PER_GAME = 0.14


def load_scoring_config() -> dict:
    """Load ESPN scoring weights from config/espn_scoring.yaml."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def estimate_batter_points(
    probs: dict[str, float],
    scoring: dict,
    pas: int = 1,
    speed_elo: float = 1500.0,
    pitcher_sb_factor: float = 1.0,
) -> float:
    """Estimate expected fantasy points for a batter.

    Args:
        probs: PA outcome probabilities (BB, K, OUT, 1B, 2B, 3B, HR)
        scoring: scoring config dict with 'batter' key
        pas: number of plate appearances (default 1 = per-PA rate)
        speed_elo: batter's speed talent ELO — scales stolen base rate
        pitcher_sb_factor: opponent pitcher's SB-allow rate vs league avg (>1 = easier to steal)

    Returns:
        expected fantasy points
    """
    rules = scoring["batter"]

    # Total bases: 1B=1, 2B=2, 3B=3, HR=4
    e_tb = (probs.get("1B", 0) * 1
            + probs.get("2B", 0) * 2
            + probs.get("3B", 0) * 3
            + probs.get("HR", 0) * 4)

    # BB and HBP (LR-3: both score +1 ESPN point and create steal opportunities)
    e_bb = probs.get("BB", 0)
    e_hbp = probs.get("HBP", 0)

    # Strikeouts (penalty)
    e_so = probs.get("K", 0)

    # SB: scale by batter speed ELO and opponent pitcher permissiveness
    speed_z = (speed_elo - SPEED_ELO_MEAN) / SPEED_ELO_STD

    # R and RBI estimated from total bases (multipliers from config; speed adjusts run rate)
    calib = scoring.get("calibration", {})
    r_per_tb = calib.get("r_per_tb", 0.40)
    rbi_per_tb = calib.get("rbi_per_tb", 0.45)
    e_runs = e_tb * r_per_tb + speed_z * 0.015  # faster batters score more runs independent of TBs
    e_rbi = e_tb * rbi_per_tb
    speed_factor = max(0.1, 1.0 + speed_z * 0.6)
    sb_rate = 0.02 * speed_factor * max(0.1, pitcher_sb_factor)
    e_sb = (probs.get("1B", 0) + e_bb + e_hbp) * sb_rate  # HBP also creates steal opportunity

    pts_per_pa = (
        e_tb * rules.get("TB", 1)
        + e_runs * rules.get("R", 1)
        + e_rbi * rules.get("RBI", 1)
        + e_bb * rules.get("BB", 1)
        + e_sb * rules.get("SB", 1)
        + e_so * rules.get("SO", -1)
    )

    return float(round(pts_per_pa * pas))


def estimate_pitcher_points(
    probs: dict[str, float],
    scoring: dict,
    innings: float = 6.0,
    win_prob: float = 0.0,
    loss_prob: float = 0.0,
) -> float:
    """Estimate expected fantasy points for a starting pitcher.

    Args:
        probs: PA outcome probabilities (from batter's perspective — inverted)
        scoring: scoring config dict with 'pitcher' key
        innings: expected innings pitched (default 6.0 for a starter)
        win_prob: probability of earning a win this start
        loss_prob: probability of earning a loss this start

    Returns:
        expected fantasy points for the start
    """
    rules = scoring["pitcher"]

    bf = innings * AVG_BF_PER_INNING

    k_per_bf = probs.get("K", 0.22)
    bb_per_bf = probs.get("BB", 0.09)
    hb_per_bf = probs.get("HBP", 0.0)
    hit_per_bf = (probs.get("1B", 0) + probs.get("2B", 0)
                  + probs.get("3B", 0) + probs.get("HR", 0))
    hr_per_bf = probs.get("HR", 0)

    e_k = k_per_bf * bf
    e_bb = bb_per_bf * bf
    e_hb = hb_per_bf * bf
    e_hits = hit_per_bf * bf
    e_hr = hr_per_bf * bf
    e_er = (e_hits + e_bb + e_hb) * 0.30

    pts = (
        innings * rules.get("IP", 3)
        + e_k * rules.get("K", 1)
        + e_hits * rules.get("H", -1)
        + e_hr * rules.get("HR", -1)
        + e_er * rules.get("ER", -1)
        + e_bb * rules.get("BB", -1)
        + e_hb * rules.get("HB", 1)
        + win_prob * rules.get("W", 5)
        + loss_prob * rules.get("L", -5)
    )

    return float(round(pts))


def estimate_reliever_points(
    probs: dict[str, float],
    scoring: dict,
    appearances: float,
    sv_per_app: float = 0.0,
    hld_per_app: float = 0.0,
    ip_per_app: float = 1.0,
) -> float:
    """Estimate expected fantasy points for a relief pitcher over a week.

    Args:
        probs: PA outcome probabilities (from batter's perspective — inverted)
        scoring: scoring config dict with 'pitcher' key
        appearances: expected number of appearances this week
        sv_per_app: historical saves per appearance
        hld_per_app: historical holds per appearance
        ip_per_app: average innings pitched per appearance

    Returns:
        expected fantasy points for the week
    """
    rules = scoring["pitcher"]

    total_ip = appearances * ip_per_app
    bf = total_ip * AVG_BF_PER_INNING

    k_per_bf = probs.get("K", 0.22)
    bb_per_bf = probs.get("BB", 0.09)
    hb_per_bf = probs.get("HBP", 0.0)
    hit_per_bf = (probs.get("1B", 0) + probs.get("2B", 0)
                  + probs.get("3B", 0) + probs.get("HR", 0))
    hr_per_bf = probs.get("HR", 0)

    e_k = k_per_bf * bf
    e_bb = bb_per_bf * bf
    e_hb = hb_per_bf * bf
    e_hits = hit_per_bf * bf
    e_hr = hr_per_bf * bf
    e_er = (e_hits + e_bb + e_hb) * 0.30
    e_sv = sv_per_app * appearances
    e_hld = hld_per_app * appearances
    # Blown saves: ~15% of save opportunities result in a blown save (MLB avg)
    BS_RATE = 0.15
    e_bs = e_sv * BS_RATE

    pts = (
        total_ip * rules.get("IP", 3)
        + e_k * rules.get("K", 1)
        + e_hits * rules.get("H", -1)
        + e_hr * rules.get("HR", -1)
        + e_er * rules.get("ER", -1)
        + e_bb * rules.get("BB", -1)
        + e_hb * rules.get("HB", 1)
        + e_sv * rules.get("SV", 5)
        + e_hld * rules.get("HD", 0)  # HD removed from config; default 0 (not 2)
        + e_bs * rules.get("BS", 0)
    )

    return float(round(pts))
