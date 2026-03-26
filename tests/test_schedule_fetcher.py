"""Tests for schedule_fetcher — MLB Stats API for weekly schedule + probable pitchers."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from src.fantasy.schedule_fetcher import (
    get_week_range,
    parse_schedule_response,
    ScheduleGame,
)


class TestGetWeekRange:
    def test_monday_input(self):
        """Monday should return Mon-Sun of that week."""
        start, end = get_week_range(date(2025, 7, 7))  # Monday
        assert start == date(2025, 7, 7)
        assert end == date(2025, 7, 13)

    def test_wednesday_input(self):
        """Wednesday should return Mon-Sun of that week."""
        start, end = get_week_range(date(2025, 7, 9))  # Wednesday
        assert start == date(2025, 7, 7)
        assert end == date(2025, 7, 13)

    def test_sunday_input(self):
        """Sunday should return Mon-Sun of that week."""
        start, end = get_week_range(date(2025, 7, 13))  # Sunday
        assert start == date(2025, 7, 7)
        assert end == date(2025, 7, 13)

    def test_week_is_7_days(self):
        start, end = get_week_range(date(2025, 8, 15))
        assert (end - start).days == 6


class TestParseScheduleResponse:
    def test_parse_single_game(self):
        data = {
            "dates": [{
                "date": "2025-07-07",
                "games": [{
                    "gamePk": 123456,
                    "teams": {
                        "away": {
                            "team": {"abbreviation": "NYY"},
                            "probablePitcher": {"id": 543037, "fullName": "Gerrit Cole"}
                        },
                        "home": {
                            "team": {"abbreviation": "BOS"},
                            "probablePitcher": {"id": 678901, "fullName": "Brayan Bello"}
                        },
                    },
                    "venue": {"name": "Fenway Park"},
                }]
            }]
        }
        games = parse_schedule_response(data)
        assert len(games) == 1
        g = games[0]
        assert g.game_date == date(2025, 7, 7)
        assert g.away_team == "NYY"
        assert g.home_team == "BOS"
        assert g.away_pitcher_id == 543037
        assert g.away_pitcher_name == "Gerrit Cole"
        assert g.home_pitcher_id == 678901

    def test_parse_no_probable_pitcher(self):
        data = {
            "dates": [{
                "date": "2025-07-07",
                "games": [{
                    "gamePk": 123456,
                    "teams": {
                        "away": {
                            "team": {"abbreviation": "NYY"},
                        },
                        "home": {
                            "team": {"abbreviation": "BOS"},
                            "probablePitcher": {"id": 678901, "fullName": "Brayan Bello"}
                        },
                    },
                    "venue": {"name": "Fenway Park"},
                }]
            }]
        }
        games = parse_schedule_response(data)
        assert len(games) == 1
        assert games[0].away_pitcher_id is None
        assert games[0].away_pitcher_name == "TBD"

    def test_parse_empty_dates(self):
        games = parse_schedule_response({"dates": []})
        assert games == []

    def test_parse_multiple_dates(self):
        data = {
            "dates": [
                {"date": "2025-07-07", "games": [
                    {"gamePk": 1, "teams": {
                        "away": {"team": {"abbreviation": "NYY"}},
                        "home": {"team": {"abbreviation": "BOS"}},
                    }, "venue": {"name": "Fenway"}},
                ]},
                {"date": "2025-07-08", "games": [
                    {"gamePk": 2, "teams": {
                        "away": {"team": {"abbreviation": "LAD"}},
                        "home": {"team": {"abbreviation": "SF"}},
                    }, "venue": {"name": "Oracle"}},
                ]},
            ]
        }
        games = parse_schedule_response(data)
        assert len(games) == 2

    def test_schedule_game_fields(self):
        g = ScheduleGame(
            game_date=date(2025, 7, 7),
            game_pk=123,
            away_team="NYY",
            home_team="BOS",
            away_pitcher_id=1,
            away_pitcher_name="Cole",
            home_pitcher_id=2,
            home_pitcher_name="Bello",
            venue="Fenway",
        )
        assert g.game_pk == 123
