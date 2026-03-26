"""Weekly projection orchestrator — combines all fantasy modules.

Flow: roster + schedule → opponent resolution → ELO lookup → matchup prediction → fantasy points.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame
from src.fantasy.opponent_resolver import resolve_opponents, PITCHER_SLOTS, INACTIVE_SLOTS
from src.fantasy.elo_lookup import EloLookup
from src.fantasy.matchup_predictor import predict_plate_appearance
from src.fantasy.fantasy_calculator import (
    estimate_batter_points,
    estimate_pitcher_points,
    load_scoring_config,
)

logger = logging.getLogger(__name__)

# Average PAs per game for a batter in the lineup
AVG_PA_PER_GAME = 3.9


@dataclass
class GameMatchup:
    game_date: date
    opponent_team: str
    opponent_pitcher_name: str
    is_home: bool
    expected_woba: float
    expected_points: float
    probabilities: dict[str, float]


@dataclass
class BatterProjection:
    player_name: str
    team: str
    slot: str
    games: list[GameMatchup]
    total_points: float = 0.0
    points_per_game: float = 0.0


@dataclass
class PitcherProjection:
    player_name: str
    team: str
    slot: str
    starts: list[GameMatchup]
    total_points: float = 0.0


@dataclass
class WeeklyProjection:
    week_start: date
    week_end: date
    batters: list[BatterProjection] = field(default_factory=list)
    pitchers: list[PitcherProjection] = field(default_factory=list)
    total_batter_points: float = 0.0
    total_pitcher_points: float = 0.0
    total_points: float = 0.0


def project_week(
    roster: list[RosterEntry],
    schedule: list[ScheduleGame],
    elo_lookup: EloLookup,
) -> WeeklyProjection:
    """Generate weekly fantasy projection.

    Args:
        roster: parsed roster entries
        schedule: weekly schedule with probable pitchers
        elo_lookup: pre-loaded ELO lookup cache

    Returns:
        WeeklyProjection with per-player breakdowns
    """
    scoring = load_scoring_config()
    matchups = resolve_opponents(roster, schedule)

    # Collect all pitcher IDs we need to look up
    pitcher_ids = [m.opponent_pitcher_id for m in matchups if m.opponent_pitcher_id]
    elo_lookup.load_batch(pitcher_ids)

    # Determine week range from schedule
    if schedule:
        week_start = min(g.game_date for g in schedule)
        week_end = max(g.game_date for g in schedule)
    else:
        week_start = week_end = date.today()

    # Group matchups by player
    batter_matchups: dict[str, list] = {}
    pitcher_matchups: dict[str, list] = {}

    for m in matchups:
        entry_key = f"{m.player_name}|{m.player_team}|{m.slot}"
        if m.slot in PITCHER_SLOTS:
            pitcher_matchups.setdefault(entry_key, []).append(m)
        else:
            batter_matchups.setdefault(entry_key, []).append(m)

    # Project batters
    batters = []
    for key, player_matchups in batter_matchups.items():
        name, team, slot = key.split("|")
        games = []

        for m in player_matchups:
            if m.opponent_pitcher_id:
                pitcher_elo = elo_lookup.get_pitcher_elo(m.opponent_pitcher_id)
            else:
                pitcher_elo = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0}

            # For batter ELO, we'd need batter ID — use name lookup or default
            # For now, use the ELO lookup by looking up any cached batter data
            batter_elo = elo_lookup.get_batter_elo(0)  # Will use defaults if not found

            # Try to find this batter's actual ELO by scanning loaded batters
            # (In production, roster entries would include player_id after fuzzy matching)
            pred = predict_plate_appearance(batter_elo, pitcher_elo)
            pts = estimate_batter_points(pred["probabilities"], scoring, pas=AVG_PA_PER_GAME)

            games.append(GameMatchup(
                game_date=m.game_date,
                opponent_team=m.opponent_team,
                opponent_pitcher_name=m.opponent_pitcher_name,
                is_home=m.is_home,
                expected_woba=pred["expected_woba"],
                expected_points=pts,
                probabilities=pred["probabilities"],
            ))

        total_pts = sum(g.expected_points for g in games)
        ppg = total_pts / len(games) if games else 0.0

        batters.append(BatterProjection(
            player_name=name, team=team, slot=slot,
            games=games, total_points=total_pts, points_per_game=ppg,
        ))

    # Project pitchers
    pitchers = []
    for key, player_matchups in pitcher_matchups.items():
        name, team, slot = key.split("|")
        starts = []

        for m in player_matchups:
            if m.opponent_pitcher_id:
                pitcher_elo = elo_lookup.get_pitcher_elo(m.opponent_pitcher_id)
            else:
                pitcher_elo = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0}

            # Pitcher prediction: use average batter as opponent
            batter_elo = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}
            pred = predict_plate_appearance(batter_elo, pitcher_elo)

            # For the pitcher's own stats, invert: high-K opponent = pitcher gets K's
            # We need the pitcher's own talent to estimate their start quality
            # Use their talent ELO to predict how opposing batters do against them
            pitcher_own_elo = elo_lookup.get_pitcher_elo(0)  # Would use pitcher's actual ID
            avg_batter = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}
            pitcher_pred = predict_plate_appearance(avg_batter, pitcher_own_elo)

            pts = estimate_pitcher_points(pitcher_pred["probabilities"], scoring, innings=6.0)

            starts.append(GameMatchup(
                game_date=m.game_date,
                opponent_team=m.opponent_team,
                opponent_pitcher_name=f"vs {m.opponent_team}",
                is_home=m.is_home,
                expected_woba=pitcher_pred["expected_woba"],
                expected_points=pts,
                probabilities=pitcher_pred["probabilities"],
            ))

        total_pts = sum(s.expected_points for s in starts)
        pitchers.append(PitcherProjection(
            player_name=name, team=team, slot=slot,
            starts=starts, total_points=total_pts,
        ))

    total_batter = sum(b.total_points for b in batters)
    total_pitcher = sum(p.total_points for p in pitchers)

    return WeeklyProjection(
        week_start=week_start,
        week_end=week_end,
        batters=sorted(batters, key=lambda b: b.total_points, reverse=True),
        pitchers=sorted(pitchers, key=lambda p: p.total_points, reverse=True),
        total_batter_points=total_batter,
        total_pitcher_points=total_pitcher,
        total_points=total_batter + total_pitcher,
    )
