"""Fetch season-level player stats from MLB Stats API and upsert into player_season_stats.

Pulls batting stats (R, RBI, TB, SB, BB, HBP, SO) and pitching stats
(IP/outs, K, W, L, SV, HLD, H, ER, BB, HBP) for all MLB players in a season.
Player IDs from the MLB Stats API match our players.player_id (MLBAM IDs).

Usage:
    python -m src.etl.fetch_player_stats          # defaults to current year
    python -m src.etl.fetch_player_stats --year 2025
"""

import argparse
import logging
import math
import os
from datetime import date

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"
PAGE_SIZE = 500


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _fetch_all(group: str, season: int) -> list[dict]:
    """Fetch all player splits for a group ('hitting' or 'pitching')."""
    all_splits = []
    offset = 0
    while True:
        url = (
            f"{MLB_STATS_BASE}/stats"
            f"?stats=season&group={group}&season={season}"
            f"&sportId=1&playerPool=All&limit={PAGE_SIZE}&offset={offset}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("stats"):
            break
        splits = data["stats"][0].get("splits", [])
        if not splits:
            break

        all_splits.extend(splits)
        total = data["stats"][0].get("totalSplits", len(all_splits))
        logger.info(f"  {group}: fetched {len(all_splits)} / {total}")

        if len(all_splits) >= total:
            break
        offset += PAGE_SIZE

    return all_splits


def _parse_ip(ip_str: str) -> int:
    """Convert '6.2' (6 innings + 2 outs) or '27.0' to total outs recorded."""
    try:
        innings, partial = str(ip_str).split(".")
        return int(innings) * 3 + int(partial)
    except (ValueError, AttributeError):
        return 0


_EMPTY_ROW_TEMPLATE = {
    "pa": 0, "total_bases": 0, "runs": 0, "rbi": 0,
    "sb": 0, "bb": 0, "hbp": 0, "so": 0,
    "hits": 0, "home_runs": 0,
    "outs_recorded": 0, "k": 0, "wins": 0, "losses": 0,
    "saves": 0, "holds": 0, "h_allowed": 0, "er": 0,
    "bb_allowed": 0, "hbp_allowed": 0, "bf": 0,
    "hr_allowed": 0, "blown_saves": 0, "complete_games": 0,
    "shutouts": 0, "balks": 0, "pickoffs": 0,
}


def build_upsert_rows(season: int) -> list[dict]:
    """Fetch hitting + pitching splits and merge into upsert rows keyed by player_id."""
    rows: dict[int, dict] = {}

    def get_row(pid: int) -> dict:
        if pid not in rows:
            rows[pid] = {"player_id": pid, "season_year": season, **_EMPTY_ROW_TEMPLATE}
        return rows[pid]

    # ── Batting ───────────────────────────────────────────────────────────────
    logger.info("Fetching batting stats...")
    for split in _fetch_all("hitting", season):
        pid = split["player"]["id"]
        s = split["stat"]
        get_row(pid).update(
            {
                "pa": s.get("plateAppearances", 0),
                "total_bases": s.get("totalBases", 0),
                "runs": s.get("runs", 0),
                "rbi": s.get("rbi", 0),
                "sb": s.get("stolenBases", 0),
                "bb": s.get("baseOnBalls", 0),
                "hbp": s.get("hitByPitch", 0),
                "so": s.get("strikeOuts", 0),
                "hits": s.get("hits", 0),
                "home_runs": s.get("homeRuns", 0),
            }
        )

    # ── Pitching ──────────────────────────────────────────────────────────────
    logger.info("Fetching pitching stats...")
    for split in _fetch_all("pitching", season):
        pid = split["player"]["id"]
        s = split["stat"]
        get_row(pid).update(
            {
                "outs_recorded": s.get("outs", 0),
                "k": s.get("strikeOuts", 0),
                "wins": s.get("wins", 0),
                "losses": s.get("losses", 0),
                "saves": s.get("saves", 0),
                "holds": s.get("holds", 0),
                "h_allowed": s.get("hits", 0),
                "er": s.get("earnedRuns", 0),
                "bb_allowed": s.get("baseOnBalls", 0),
                "hbp_allowed": s.get("hitByPitch", 0),
                "bf": s.get("battersFaced", 0),
                "hr_allowed": s.get("homeRuns", 0),
                "blown_saves": s.get("blownSaves", 0),
                "complete_games": s.get("completeGames", 0),
                "shutouts": s.get("shutouts", 0),
                "balks": s.get("balks", 0),
                "pickoffs": s.get("pickoffs", 0),
            }
        )

    return list(rows.values())


def upsert_rows(sb, rows: list[dict], batch_size: int = 500) -> int:
    """Upsert rows into player_season_stats. Returns count of rows upserted."""
    # Only upsert players that exist in our players table (paginate past 1000-row limit)
    existing_ids: set[int] = set()
    offset = 0
    while True:
        resp = sb.table("players").select("player_id").range(offset, offset + 999).execute()
        existing_ids.update(r["player_id"] for r in resp.data or [])
        if len(resp.data or []) < 1000:
            break
        offset += 1000

    filtered = [r for r in rows if r["player_id"] in existing_ids]
    skipped = len(rows) - len(filtered)
    if skipped:
        logger.info(f"  Skipping {skipped} players not in our players table")

    count = 0
    for i in range(0, len(filtered), batch_size):
        batch = filtered[i : i + batch_size]
        sb.table("player_season_stats").upsert(batch, on_conflict="player_id,season_year").execute()
        count += len(batch)
        logger.info(f"  Upserted {count}/{len(filtered)} rows")

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()

    season = args.year
    logger.info(f"Fetching {season} season stats from MLB Stats API...")

    rows = build_upsert_rows(season)
    logger.info(f"Built {len(rows)} player rows ({season})")

    sb = _get_supabase()
    total = upsert_rows(sb, rows)
    logger.info(f"Done. Upserted {total} rows into player_season_stats.")


if __name__ == "__main__":
    main()
