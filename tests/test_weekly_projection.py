"""Tests for weekly_projection — orchestrator combining all fantasy modules."""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from src.fantasy.weekly_projection import (
    project_week,
    BatterProjection,
    PitcherProjection,
    WeeklyProjection,
)
from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame


@pytest.fixture
def sample_roster():
    return [
        RosterEntry(slot="OF", name="Aaron Judge", team="NYY"),
        RosterEntry(slot="SP", name="Gerrit Cole", team="NYY"),
        RosterEntry(slot="IL", name="Mike Trout", team="LAA"),
    ]


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
            away_pitcher_id=None, away_pitcher_name="TBD",
            home_pitcher_id=None, home_pitcher_name="TBD",
            venue="Yankee Stadium",
        ),
    ]


@pytest.fixture
def mock_elo_lookup():
    lookup = MagicMock()
    lookup.get_batter_elo.return_value = {
        "contact": 1520.0, "power": 1550.0, "discipline": 1750.0,
        "speed": 1500.0, "clutch": 1500.0,
    }
    lookup.get_pitcher_elo.return_value = {
        "stuff": 1600.0, "bip_suppression": 1510.0, "command": 1700.0, "clutch": 1500.0,
    }
    lookup.get_team_elo.return_value = 1500.0
    lookup.get_recent_form_adjustment.return_value = 1.0
    return lookup


class TestProjectWeek:

    def test_returns_weekly_projection(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        assert isinstance(result, WeeklyProjection)

    def test_batters_included(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        assert len(result.batters) > 0
        names = [b.player_name for b in result.batters]
        assert "Aaron Judge" in names

    def test_pitchers_included(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        # Cole is probable pitcher in game 1
        cole = [p for p in result.pitchers if p.player_name == "Gerrit Cole"]
        assert len(cole) == 1

    def test_il_excluded(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        all_names = [b.player_name for b in result.batters] + [p.player_name for p in result.pitchers]
        assert "Mike Trout" not in all_names

    def test_batter_projection_fields(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        b = result.batters[0]
        assert hasattr(b, "player_name")
        assert hasattr(b, "team")
        assert hasattr(b, "slot")
        assert hasattr(b, "games")
        assert hasattr(b, "total_points")
        assert hasattr(b, "points_per_game")

    def test_pitcher_projection_fields(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        if result.pitchers:
            p = result.pitchers[0]
            assert hasattr(p, "player_name")
            assert hasattr(p, "team")
            assert hasattr(p, "starts")
            assert hasattr(p, "total_points")

    def test_total_points_positive(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        assert result.total_batter_points > 0

    def test_week_dates_set(self, sample_roster, sample_schedule, mock_elo_lookup):
        result = project_week(sample_roster, sample_schedule, mock_elo_lookup)
        assert result.week_start is not None
        assert result.week_end is not None
