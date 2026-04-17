"""Fetch per-player SB/CS counts for a date from MLB API box scores.

Uses the schedule+boxscore hydration endpoint to get all games in one call.
"""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


def _get_game_pks_for_date(date_str: str) -> list[dict]:
    """Return list of {game_pk, home_team, away_team} for regular-season games on date_str."""
    url = f"{MLB_STATS_BASE}/schedule?sportId=1&date={date_str}&gameType=R"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            games.append({
                "game_pk": int(game["gamePk"]),
                "home_team": game.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", ""),
                "away_team": game.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", ""),
            })
    return games


def _get_sb_cs_from_boxscore(game_pk: int, home_team: str, away_team: str, date_str: str) -> list[dict]:
    """Fetch boxscore for game_pk and return per-player SB/CS rows."""
    url = f"{MLB_STATS_BASE}/game/{game_pk}/boxscore"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Prefer abbreviations from the boxscore itself (schedule response lacks them)
    home_team = data.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", home_team) or home_team
    away_team = data.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", away_team) or away_team

    results = []
    for side in ("home", "away"):
        players = data.get("teams", {}).get(side, {}).get("players", {})
        for player_data in players.values():
            batting = player_data.get("stats", {}).get("batting", {})
            sb = int(batting.get("stolenBases", 0) or 0)
            cs = int(batting.get("caughtStealing", 0) or 0)
            if sb == 0 and cs == 0:
                continue
            pid = player_data.get("person", {}).get("id")
            if pid is None:
                continue
            results.append({
                "player_id": int(pid),
                "game_pk": game_pk,
                "game_date": date_str,
                "home_team": home_team,
                "away_team": away_team,
                "sb": sb,
                "cs": cs,
            })
    return results


def fetch_speed_events_for_date(target_date: date) -> list[dict]:
    """Return per-player SB/CS for every game on target_date.

    Returns list of dicts: {player_id, game_pk, home_team, away_team, sb, cs}
    Only includes players with sb > 0 or cs > 0.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    games = _get_game_pks_for_date(date_str)
    if not games:
        logger.info(f"  MLB API: no regular-season games on {date_str}")
        return []

    results = []
    for game in games:
        try:
            rows = _get_sb_cs_from_boxscore(
                game["game_pk"], game["home_team"], game["away_team"], date_str
            )
            results.extend(rows)
        except Exception as e:
            logger.warning(f"  Boxscore fetch failed for game {game['game_pk']}: {e}")

    logger.info(f"  MLB API box scores: {len(results)} player-games with SB/CS on {date_str}")
    return results
