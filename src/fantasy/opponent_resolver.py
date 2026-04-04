"""Map roster players to their weekly opponents via schedule.

Resolves which pitcher each batter faces and which lineup each pitcher faces,
based on team affiliations and the weekly schedule.
"""

from dataclasses import dataclass
from datetime import date

from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame

INACTIVE_SLOTS = {"IL", "IL+", "DL", "NA"}
PITCHER_SLOTS = {"SP", "RP", "P"}


@dataclass
class MatchupSlot:
    player_id: int | None
    player_name: str
    player_team: str
    slot: str
    game_date: date
    game_pk: int
    opponent_team: str
    opponent_pitcher_id: int | None
    opponent_pitcher_name: str
    is_home: bool
    venue: str
    is_start: bool = True  # False for RP relief appearances


def resolve_opponents(
    roster: list[RosterEntry],
    schedule: list[ScheduleGame],
) -> list[MatchupSlot]:
    """Resolve roster × schedule into matchup slots.

    For batters: finds opposing pitcher for each game their team plays.
    For pitchers: finds games where they are the probable pitcher.

    Args:
        roster: parsed roster entries
        schedule: weekly schedule with probable pitchers

    Returns:
        list of MatchupSlot, sorted by date then player name
    """
    # Index schedule by team
    team_games: dict[str, list[ScheduleGame]] = {}
    for game in schedule:
        team_games.setdefault(game.away_team, []).append(game)
        team_games.setdefault(game.home_team, []).append(game)

    matchups = []

    for entry in roster:
        if entry.slot in INACTIVE_SLOTS:
            continue
        if not entry.team:
            continue

        games = team_games.get(entry.team, [])

        if entry.slot == "RP":
            # Relief pitchers: include ALL team games as potential appearance slots
            for game in games:
                is_home = game.home_team == entry.team
                m = _make_matchup(entry, game, is_home)
                m.is_start = False
                matchups.append(m)
        elif entry.slot in PITCHER_SLOTS:
            # SP / P: only include games where they are the probable starter
            for game in games:
                is_home = game.home_team == entry.team
                if is_home and game.home_pitcher_name == entry.name:
                    matchups.append(_make_matchup(entry, game, is_home))
                elif not is_home and game.away_pitcher_name == entry.name:
                    matchups.append(_make_matchup(entry, game, is_home))
        else:
            # For batters: include all games their team plays
            for game in games:
                is_home = game.home_team == entry.team
                matchups.append(_make_matchup(entry, game, is_home))

    matchups.sort(key=lambda m: (m.game_date, m.player_name))
    return matchups


def _make_matchup(entry: RosterEntry, game: ScheduleGame, is_home: bool) -> MatchupSlot:
    """Create a MatchupSlot from a roster entry and game."""
    if is_home:
        opp_team = game.away_team
        opp_pitcher_id = game.away_pitcher_id
        opp_pitcher_name = game.away_pitcher_name
    else:
        opp_team = game.home_team
        opp_pitcher_id = game.home_pitcher_id
        opp_pitcher_name = game.home_pitcher_name

    return MatchupSlot(
        player_id=entry.player_id,
        player_name=entry.name,
        player_team=entry.team,
        slot=entry.slot,
        game_date=game.game_date,
        game_pk=game.game_pk,
        opponent_team=opp_team,
        opponent_pitcher_id=opp_pitcher_id,
        opponent_pitcher_name=opp_pitcher_name,
        is_home=is_home,
        venue=game.venue,
    )
