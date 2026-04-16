"""One-time repair script: populate players.team for any player with an empty team.

Queries the players table for rows where team is '' or NULL, then calls the MLB
Stats API /people?personIds=... endpoint in batches of 100 to get currentTeam
abbreviations, and upserts the results back.

Usage:
    python scripts/repair_player_teams.py
    python scripts/repair_player_teams.py --all   # refresh ALL players, not just empty
"""

import argparse
import logging
import os

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
BATCH_SIZE = 100


def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def fetch_team_id_map() -> dict[int, str]:
    """Fetch all MLB teams and return {team_id: abbreviation}."""
    url = f"{MLB_API_BASE}/teams?sportId=1"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    teams = resp.json().get("teams", [])
    return {t["id"]: t["abbreviation"] for t in teams if "abbreviation" in t}


def fetch_teams_batch(player_ids: list[int], team_id_map: dict[int, str]) -> dict[int, str]:
    """Call /people?personIds=... for up to 100 IDs. Returns {player_id: team_abbrev}."""
    ids_str = ",".join(str(i) for i in player_ids)
    url = f"{MLB_API_BASE}/people?personIds={ids_str}&hydrate=currentTeam"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"MLB API error for batch: {e}")
        return {}

    result = {}
    for person in data.get("people", []):
        pid = person.get("id")
        team_id = person.get("currentTeam", {}).get("id")
        if pid and team_id:
            abbrev = team_id_map.get(team_id, "")
            if abbrev:
                result[pid] = abbrev
    return result


def repair(all_players: bool = False) -> None:
    sb = get_supabase()

    # Fetch players to fix
    logger.info("Querying players table...")
    resp = sb.table("players").select("player_id,team,full_name").execute()
    rows = resp.data

    if all_players:
        to_fix = rows
        logger.info(f"Refreshing ALL {len(to_fix)} players")
    else:
        to_fix = [r for r in rows if not r.get("team")]
        logger.info(f"Found {len(to_fix)} players with empty team (out of {len(rows)} total)")

    if not to_fix:
        logger.info("Nothing to fix.")
        return

    ids = [r["player_id"] for r in to_fix]
    updates: dict[int, str] = {}

    logger.info("Fetching MLB team abbreviation map...")
    team_id_map = fetch_team_id_map()
    logger.info(f"  Loaded {len(team_id_map)} teams")

    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i : i + BATCH_SIZE]
        logger.info(f"Fetching batch {i // BATCH_SIZE + 1} ({len(batch)} players)...")
        team_map = fetch_teams_batch(batch, team_id_map)
        updates.update(team_map)
        logger.info(f"  Got teams for {len(team_map)}/{len(batch)} players in batch")

    # Update team field per player (update, not upsert, to avoid clobbering other fields)
    to_update = [(pid, team) for pid, team in updates.items() if team]
    logger.info(f"Updating {len(to_update)} players...")

    for i, (pid, team) in enumerate(to_update):
        sb.table("players").update({"team": team}).eq("player_id", pid).execute()
        if (i + 1) % 100 == 0:
            logger.info(f"  {i + 1}/{len(to_update)} updated")

    fixed = len(to_update)
    skipped = len(to_fix) - fixed
    logger.info(f"Done. Updated {fixed} players. {skipped} had no team in MLB API (likely inactive/minor league).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Refresh ALL players, not just empty-team ones")
    args = parser.parse_args()
    repair(all_players=args.all)
