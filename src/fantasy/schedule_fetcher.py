"""Fetch MLB schedule + probable pitchers from MLB Stats API.

Uses statsapi.mlb.com/api/v1/schedule for a given week (Mon-Sun).
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"


@dataclass
class ScheduleGame:
    game_date: date
    game_pk: int
    away_team: str
    home_team: str
    away_pitcher_id: int | None
    away_pitcher_name: str
    home_pitcher_id: int | None
    home_pitcher_name: str
    venue: str


def get_week_range(ref_date: date) -> tuple[date, date]:
    """Return (Monday, Sunday) for the week containing ref_date."""
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def parse_schedule_response(data: dict) -> list[ScheduleGame]:
    """Parse MLB Stats API schedule response into ScheduleGame list."""
    games = []
    for date_entry in data.get("dates", []):
        game_date = date.fromisoformat(date_entry["date"])
        for game in date_entry.get("games", []):
            teams = game.get("teams", {})
            away = teams.get("away", {})
            home = teams.get("home", {})

            away_pitcher = away.get("probablePitcher", {})
            home_pitcher = home.get("probablePitcher", {})

            games.append(ScheduleGame(
                game_date=game_date,
                game_pk=game.get("gamePk", 0),
                away_team=away.get("team", {}).get("abbreviation", ""),
                home_team=home.get("team", {}).get("abbreviation", ""),
                away_pitcher_id=away_pitcher.get("id"),
                away_pitcher_name=away_pitcher.get("fullName", "TBD"),
                home_pitcher_id=home_pitcher.get("id"),
                home_pitcher_name=home_pitcher.get("fullName", "TBD"),
                venue=game.get("venue", {}).get("name", ""),
            ))

    return games


def fetch_week_schedule(ref_date: date) -> list[ScheduleGame]:
    """Fetch MLB schedule for the week containing ref_date.

    Args:
        ref_date: any date within the target week

    Returns:
        list of ScheduleGame for Mon-Sun of that week
    """
    start, end = get_week_range(ref_date)
    params = {
        "sportId": 1,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "hydrate": "probablePitcher,team",
        "gameType": "R",
    }

    logger.info(f"Fetching MLB schedule: {start} → {end}")
    resp = requests.get(MLB_SCHEDULE_URL, params=params, timeout=15)
    resp.raise_for_status()

    games = parse_schedule_response(resp.json())
    logger.info(f"  {len(games)} games found")
    return games
