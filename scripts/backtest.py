"""Backtesting harness: evaluate projection accuracy against historical plate appearances.

Computes per-player and aggregate metrics:
  - Brier score per outcome bucket
  - Multi-class log-loss
  - Calibration (predicted P vs actual rate in decile bins)
  - Fantasy point prediction error (predicted weekly pts vs actual ESPN pts)

Usage:
    python scripts/backtest.py [--season 2025] [--sample 50000] [--weeks 10]

Output:
    Prints aggregate metrics to stdout.
    Saves per-player error CSV to tasks/backtest_results.csv.
"""

import os
import sys
import math
import argparse
import logging
from datetime import date, timedelta
from collections import defaultdict

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.fantasy.matchup_predictor import predict_plate_appearance, LEAGUE_AVG_WOBA
from src.fantasy.fantasy_calculator import (
    estimate_batter_points,
    load_scoring_config,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OUTCOME_MAP = {
    'BB': 'BB', 'IBB': 'BB', 'HBP': 'HBP',
    'StrikeOut': 'K',
    'Single': '1B', 'Double': '2B', 'Triple': '3B', 'HR': 'HR',
    'OUT': 'OUT', 'FC': 'OUT', 'GIDP': 'OUT',
    'POPUP': 'OUT', 'GROUNDOUT': 'OUT', 'SAC': 'OUT', 'E': 'OUT',
}
OUTCOMES = ['BB', 'HBP', 'K', 'OUT', '1B', '2B', '3B', 'HR']
DEFAULT_BATTER_ELO = {'contact': 1504.5, 'power': 1468.6, 'discipline': 1700.3}
DEFAULT_PITCHER_ELO = {'stuff': 1587.3, 'bip_suppression': 1513.3, 'command': 1681.1}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

PAGE_SIZE = 1_000  # Supabase PostgREST max rows per request


def load_plate_appearances(supabase, limit: int) -> pd.DataFrame:
    logger.info(f'Loading up to {limit:,} plate appearances...')
    all_rows = []
    offset = 0
    while len(all_rows) < limit:
        resp = (
            supabase.table('plate_appearances')
            .select('pa_id, batter_id, pitcher_id, game_date, result_type')
            .not_.is_('batter_id', 'null')
            .not_.is_('pitcher_id', 'null')
            .not_.is_('game_date', 'null')
            .order('game_date', desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        page = resp.data or []
        if not page:
            break
        all_rows.extend(page)
        offset += len(page)
        if len(page) < PAGE_SIZE:
            break  # last page
    df = pd.DataFrame(all_rows[:limit])
    if df.empty:
        return df
    df['outcome'] = df['result_type'].map(OUTCOME_MAP)
    df = df.dropna(subset=['outcome'])
    df['game_date'] = pd.to_datetime(df['game_date']).dt.date
    logger.info(f'Loaded {len(df):,} PAs with outcome labels')
    return df


def load_player_elos(supabase, player_ids: list[int]) -> tuple[dict, dict]:
    """Returns (batter_elos, pitcher_elos) dicts keyed by player_id."""
    batter_elos: dict[int, dict] = {}
    pitcher_elos: dict[int, dict] = {}

    batch_size = 200
    for i in range(0, len(player_ids), batch_size):
        batch = player_ids[i:i + batch_size]
        resp = (
            supabase.table('talent_player_current')
            .select('player_id, player_role, talent_type, season_elo')
            .in_('player_id', batch)
            .execute()
        )
        for row in (resp.data or []):
            pid = row['player_id']
            dim = row['talent_type']
            elo = float(row['season_elo'] or 1500.0)
            if row['player_role'] == 'batter':
                batter_elos.setdefault(pid, {})[dim] = elo
            else:
                pitcher_elos.setdefault(pid, {})[dim] = elo

    logger.info(f'Loaded ELOs for {len(batter_elos):,} batters and {len(pitcher_elos):,} pitchers')
    return batter_elos, pitcher_elos


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

def get_batter_dict(batter_elos: dict, pid: int) -> dict:
    if pid in batter_elos:
        dims = batter_elos[pid]
        return {
            'contact': dims.get('contact', DEFAULT_BATTER_ELO['contact']),
            'power': dims.get('power', DEFAULT_BATTER_ELO['power']),
            'discipline': dims.get('discipline', DEFAULT_BATTER_ELO['discipline']),
        }
    return dict(DEFAULT_BATTER_ELO)


def get_pitcher_dict(pitcher_elos: dict, pid: int) -> dict:
    if pid in pitcher_elos:
        dims = pitcher_elos[pid]
        return {
            'stuff': dims.get('stuff', DEFAULT_PITCHER_ELO['stuff']),
            'bip_suppression': dims.get('bip_suppression', DEFAULT_PITCHER_ELO['bip_suppression']),
            'command': dims.get('command', DEFAULT_PITCHER_ELO['command']),
        }
    return dict(DEFAULT_PITCHER_ELO)


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def compute_log_loss(pred_probs: list[dict], outcomes: list[str]) -> float:
    total = 0.0
    for probs, outcome in zip(pred_probs, outcomes):
        p = max(1e-9, probs.get(outcome, 1e-9))
        total -= math.log(p)
    return total / len(pred_probs)


def compute_brier_scores(pred_probs: list[dict], outcomes: list[str]) -> dict[str, float]:
    scores = defaultdict(list)
    for probs, outcome in zip(pred_probs, outcomes):
        for o in OUTCOMES:
            p_pred = probs.get(o, 0.0)
            actual = 1.0 if outcome == o else 0.0
            scores[o].append((p_pred - actual) ** 2)
    return {o: float(np.mean(v)) for o, v in scores.items()}


def compute_calibration(pred_probs: list[dict], outcomes: list[str], outcome: str, n_bins: int = 10) -> pd.DataFrame:
    """Predicted P(outcome) vs actual rate in n_bins probability deciles."""
    p_list = [probs.get(outcome, 0.0) for probs in pred_probs]
    a_list = [1.0 if o == outcome else 0.0 for o in outcomes]
    df = pd.DataFrame({'predicted': p_list, 'actual': a_list})
    df['bin'] = pd.qcut(df['predicted'], q=n_bins, duplicates='drop')
    return df.groupby('bin').agg(
        mean_predicted=('predicted', 'mean'),
        mean_actual=('actual', 'mean'),
        count=('actual', 'count'),
    ).reset_index()


def compute_fantasy_point_error(
    pa_df: pd.DataFrame,
    pred_probs: list[dict],
    scoring: dict,
) -> pd.DataFrame:
    """Per-player weekly fantasy point prediction vs actual.

    Actual points are computed by scoring observed outcomes.
    Predicted points use expected probabilities × PAs.
    """
    scoring_rules = scoring['batter']

    # Actual per-PA points from observed outcomes
    outcome_pts = {
        'BB': scoring_rules.get('BB', 1),
        'HBP': scoring_rules.get('HBP', 1),
        'K': scoring_rules.get('SO', -1),
        'OUT': 0.0,
        '1B': scoring_rules.get('TB', 1) * 1 + scoring_rules.get('R', 1) * 0.40 + scoring_rules.get('RBI', 1) * 0.45,
        '2B': scoring_rules.get('TB', 1) * 2 + scoring_rules.get('R', 1) * 0.40 + scoring_rules.get('RBI', 1) * 0.45,
        '3B': scoring_rules.get('TB', 1) * 3 + scoring_rules.get('R', 1) * 0.40 + scoring_rules.get('RBI', 1) * 0.45,
        'HR': scoring_rules.get('TB', 1) * 4 + scoring_rules.get('R', 1) * 0.40 + scoring_rules.get('RBI', 1) * 0.45,
    }

    result_df = pa_df[['batter_id', 'game_date', 'outcome']].copy()
    result_df['actual_pts'] = result_df['outcome'].map(outcome_pts).fillna(0.0)
    result_df['pred_pts'] = [
        estimate_batter_points(p, scoring, pas=1) for p in pred_probs
    ]

    # Weekly aggregate by batter
    result_df['week_start'] = result_df['game_date'].apply(
        lambda d: d - timedelta(days=d.weekday())
    )
    weekly = (
        result_df.groupby(['batter_id', 'week_start'])
        .agg(actual_pts=('actual_pts', 'sum'), pred_pts=('pred_pts', 'sum'), pa_count=('actual_pts', 'count'))
        .reset_index()
    )
    weekly['error'] = weekly['pred_pts'] - weekly['actual_pts']
    weekly['abs_error'] = weekly['error'].abs()
    return weekly


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Backtest projection accuracy')
    parser.add_argument('--sample', type=int, default=50_000, help='PA sample size')
    parser.add_argument('--calibration-outcome', default='HR', help='Outcome for calibration plot')
    parser.add_argument('--output', default='tasks/backtest_results.csv', help='Per-player error CSV path')
    args = parser.parse_args()

    supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
    scoring = load_scoring_config()

    # Load data
    pa_df = load_plate_appearances(supabase, args.sample)
    if pa_df.empty:
        logger.error('No plate appearances loaded. Check DB connection.')
        return

    all_ids = list(set(pa_df['batter_id'].tolist() + pa_df['pitcher_id'].tolist()))
    batter_elos, pitcher_elos = load_player_elos(supabase, all_ids)

    # Predict
    logger.info('Running predictions...')
    pred_probs = []
    for _, row in pa_df.iterrows():
        b = get_batter_dict(batter_elos, row['batter_id'])
        p = get_pitcher_dict(pitcher_elos, row['pitcher_id'])
        result = predict_plate_appearance(b, p)
        pred_probs.append(result['probabilities'])

    outcomes = pa_df['outcome'].tolist()

    # --- Aggregate metrics ---
    ll = compute_log_loss(pred_probs, outcomes)
    brier = compute_brier_scores(pred_probs, outcomes)
    print(f'\n=== Aggregate Metrics ({len(pa_df):,} PAs) ===')
    print(f'Log-loss:     {ll:.5f}  (naive baseline ≈ {-math.log(1/len(OUTCOMES)):.5f})')
    print('\nBrier scores per outcome:')
    for o, s in sorted(brier.items()):
        actual_rate = outcomes.count(o) / len(outcomes)
        print(f'  {o:4s}: {s:.6f}  (actual rate {actual_rate:.4f})')

    # --- Calibration ---
    cal = compute_calibration(pred_probs, outcomes, args.calibration_outcome)
    print(f'\nCalibration for P({args.calibration_outcome}):')
    print(cal.to_string(index=False))

    # --- Fantasy point error ---
    weekly = compute_fantasy_point_error(pa_df, pred_probs, scoring)
    mae = weekly['abs_error'].mean()
    rmse = (weekly['error'] ** 2).mean() ** 0.5
    print(f'\nWeekly fantasy point error (per player-week):')
    print(f'  MAE:  {mae:.2f} pts')
    print(f'  RMSE: {rmse:.2f} pts')
    print(f'  N player-weeks: {len(weekly):,}')

    # --- Save per-player output ---
    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), args.output)
    weekly.to_csv(out_path, index=False)
    logger.info(f'Per-player weekly error saved to {out_path}')


if __name__ == '__main__':
    main()
