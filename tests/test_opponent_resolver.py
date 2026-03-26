"""Tests for opponent_resolver — roster × schedule → matchup tuples."""

import pytest
from datetime import date
from src.fantasy.opponent_resolver import resolve_opponents, MatchupSlot
from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame


@pytest.fixture
def sample_schedule():
    return [
        ScheduleGame(
            game_date=date(2025, 7, 7), game_pk=1,
            away_team="NYY", home_team="BOS",
            away_pitcher_id=543037, away_pitcher_name="Gerrit Cole",
            home_pitcher_id=678901, home_pitcher_name="Brayan Bello",
            venue="Fenway Park",
        ),
        ScheduleGame(
            game_date=date(2025, 7, 8), game_pk=2,
            away_team="BOS", home_team="NYY",
            away_pitcher_id=678901, away_pitcher_name="Brayan Bello",
            home_pitcher_id=543037, home_pitcher_name="Gerrit Cole",
            venue="Yankee Stadium",
        ),
        ScheduleGame(
            game_date=date(2025, 7, 7), game_pk=3,
            away_team="LAD", home_team="SF",
            away_pitcher_id=None, away_pitcher_name="TBD",
            home_pitcher_id=999, home_pitcher_name="Logan Webb",
            venue="Oracle Park",
        ),
    ]


class TestResolveOpponents:

    def test_batter_gets_opposing_pitchers(self, sample_schedule):
        roster = [RosterEntry(slot="OF", name="Aaron Judge", team="NYY")]
        matchups = resolve_opponents(roster, sample_schedule)
        # NYY plays 2 games (vs BOS at Fenway, vs BOS at Yankee)
        judge_matchups = [m for m in matchups if m.player_name == "Aaron Judge"]
        assert len(judge_matchups) == 2

    def test_batter_facing_correct_pitcher(self, sample_schedule):
        roster = [RosterEntry(slot="OF", name="Aaron Judge", team="NYY")]
        matchups = resolve_opponents(roster, sample_schedule)
        # Game 1: NYY away at BOS → Judge faces home pitcher Bello
        game1 = [m for m in matchups if m.game_date == date(2025, 7, 7)][0]
        assert game1.opponent_pitcher_name == "Brayan Bello"
        assert game1.opponent_pitcher_id == 678901

    def test_pitcher_faces_opposing_lineup(self, sample_schedule):
        roster = [RosterEntry(slot="SP", name="Gerrit Cole", team="NYY")]
        matchups = resolve_opponents(roster, sample_schedule)
        cole = [m for m in matchups if m.player_name == "Gerrit Cole"]
        # Cole is the away pitcher in game 1 (NYY at BOS)
        # Cole is the home pitcher in game 2 (BOS at NYY)
        # He's a roster SP, so we track his starts — both games have him as probable
        assert len(cole) == 2

    def test_no_games_for_team(self, sample_schedule):
        roster = [RosterEntry(slot="1B", name="Freddie Freeman", team="ATL")]
        matchups = resolve_opponents(roster, sample_schedule)
        assert len(matchups) == 0

    def test_il_players_excluded(self, sample_schedule):
        roster = [
            RosterEntry(slot="OF", name="Aaron Judge", team="NYY"),
            RosterEntry(slot="IL", name="Mike Trout", team="LAA"),
        ]
        matchups = resolve_opponents(roster, sample_schedule)
        trout = [m for m in matchups if m.player_name == "Mike Trout"]
        assert len(trout) == 0

    def test_home_away_correct(self, sample_schedule):
        roster = [RosterEntry(slot="OF", name="Aaron Judge", team="NYY")]
        matchups = resolve_opponents(roster, sample_schedule)
        game1 = [m for m in matchups if m.game_date == date(2025, 7, 7)][0]
        assert game1.is_home is False  # NYY is away team in game 1
        game2 = [m for m in matchups if m.game_date == date(2025, 7, 8)][0]
        assert game2.is_home is True  # NYY is home team in game 2

    def test_matchup_slot_fields(self, sample_schedule):
        roster = [RosterEntry(slot="OF", name="Aaron Judge", team="NYY")]
        matchups = resolve_opponents(roster, sample_schedule)
        m = matchups[0]
        assert hasattr(m, "player_name")
        assert hasattr(m, "player_team")
        assert hasattr(m, "slot")
        assert hasattr(m, "game_date")
        assert hasattr(m, "opponent_team")
        assert hasattr(m, "opponent_pitcher_id")
        assert hasattr(m, "opponent_pitcher_name")
        assert hasattr(m, "is_home")
        assert hasattr(m, "venue")
