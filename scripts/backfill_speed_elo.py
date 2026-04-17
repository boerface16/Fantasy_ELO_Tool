"""Backfill speed ELO for one or more seasons from scratch.

Deletes all existing speed ELO data, then rebuilds cleanly by processing:
  - Statcast events (3B) from existing plate_appearances
  - SB/CS events from MLB API box scores

All events are applied in chronological order so reliability ramps correctly.

Usage:
    python scripts/backfill_speed_elo.py --season 2025
    python scripts/backfill_speed_elo.py --start-date 2025-03-25 --end-date 2026-04-16
    python scripts/backfill_speed_elo.py --season 2026 --dry-run
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

from src.engine.multi_elo_config import MultiEloConfig
from src.engine.multi_elo_engine import MultiEloEngine
from src.etl.fetch_mlb_box_scores import fetch_speed_events_for_date

_config = MultiEloConfig()
_engine = MultiEloEngine(config=_config)
K_SPEED = _config.get_batter_k_factor("speed")
SCALE_SPEED = _config.get_batter_scale("speed")


def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _reliability(event_count: int) -> float:
    return _engine.calculate_reliability(event_count, "speed")


def _delta(result_type: str, event_count: int) -> float:
    """Speed ELO delta for a single event."""
    rel = _reliability(event_count)
    if result_type == "SB":
        return K_SPEED * SCALE_SPEED * 1.0 * 0.5 * rel       # +1.0 weight
    if result_type == "CS":
        return K_SPEED * SCALE_SPEED * 1.25 * (-0.5) * rel    # -1.25 weight
    if result_type == "PKO":
        return K_SPEED * SCALE_SPEED * 0.5 * (-0.5) * rel     # -0.5 weight
    if result_type == "Triple":
        return K_SPEED * SCALE_SPEED * 0.5 * 0.5 * rel        # +0.5 weight
    return 0.0


def _synthetic_pa_id(game_pk: int, seq: int) -> int:
    return game_pk * 1_000_000 + 950_000 + seq


def get_game_dates(client, seasons: list[int],
                   start_date: str | None = None,
                   end_date: str | None = None) -> list[str]:
    dates: set[str] = set()
    for season in seasons:
        offset = 0
        while True:
            q = (
                client.table("plate_appearances")
                .select("game_date")
                .eq("season_year", season)
            )
            if start_date:
                q = q.gte("game_date", start_date)
            if end_date:
                q = q.lte("game_date", end_date)
            rows = (q.range(offset, offset + 999).execute().data) or []
            dates.update(r["game_date"] for r in rows)
            if len(rows) < 1000:
                break
            offset += 1000
    return sorted(dates)


def get_statcast_speed_events(client, date_str: str) -> list[dict]:
    """Return Triple PA rows for the date."""
    rows = (
        client.table("plate_appearances")
        .select("pa_id,game_pk,batter_id,result_type,home_team,away_team")
        .eq("game_date", date_str)
        .eq("result_type", "Triple")
        .execute()
        .data
    ) or []
    return [{**r, "speed_type": "Triple"} for r in rows]


def get_known_player_ids(client) -> set[int]:
    known: set[int] = set()
    offset = 0
    while True:
        rows = (
            client.table("players")
            .select("player_id")
            .range(offset, offset + 999)
            .execute()
            .data
        ) or []
        known.update(r["player_id"] for r in rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return known


def reset_speed_data(client, seasons: list[int]):
    logger.info(f"Resetting speed ELO data for seasons: {seasons}...")

    for season in seasons:
        # Must delete talent_pa_detail BEFORE plate_appearances (FK constraint)
        offset = 0
        all_pa_ids = []
        while True:
            rows = (
                client.table("plate_appearances")
                .select("pa_id")
                .eq("season_year", season)
                .range(offset, offset + 999)
                .execute()
                .data
            ) or []
            all_pa_ids.extend(r["pa_id"] for r in rows)
            if len(rows) < 1000:
                break
            offset += 1000

        # Batch size 500 keeps request count well under the HTTP/2 stream limit (~10k).
        # Reconnect every 900 batches as a safety net in case of very large seasons.
        batch_size = 500
        for idx, i in enumerate(range(0, len(all_pa_ids), batch_size)):
            if idx > 0 and idx % 900 == 0:
                client = get_supabase()
            client.table("talent_pa_detail").delete().in_(
                "pa_id", all_pa_ids[i:i + batch_size]
            ).eq("talent_type", "speed").execute()
        logger.info(f"  [{season}] Deleted speed talent_pa_detail rows (checked {len(all_pa_ids)} pa_ids)")

        # elo_pa_detail also has a FK to plate_appearances — must delete before plate_appearances
        for idx, i in enumerate(range(0, len(all_pa_ids), batch_size)):
            if idx > 0 and idx % 900 == 0:
                client = get_supabase()
            client.table("elo_pa_detail").delete().in_(
                "pa_id", all_pa_ids[i:i + batch_size]
            ).execute()
        logger.info(f"  [{season}] Deleted elo_pa_detail rows (checked {len(all_pa_ids)} pa_ids)")

        client.table("plate_appearances").delete().eq("season_year", season).in_(
            "result_type", ["SB", "CS", "PKO"]
        ).execute()
        logger.info(f"  [{season}] Deleted SB/CS plate_appearances")

        client.table("talent_daily_ohlc").delete().eq("talent_type", "speed").eq(
            "elo_type", "SEASON"
        ).gte("game_date", f"{season}-01-01").lte("game_date", f"{season}-12-31").execute()
        logger.info(f"  [{season}] Deleted speed talent_daily_ohlc")

    # Reset talent_player_current speed rows to 1500
    offset = 0
    reset_records = []
    while True:
        rows = (
            client.table("talent_player_current")
            .select("player_id")
            .eq("talent_type", "speed")
            .eq("player_role", "batter")
            .range(offset, offset + 999)
            .execute()
            .data
        ) or []
        reset_records.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    reset_batch = [
        {
            "player_id": r["player_id"],
            "player_role": "batter",
            "talent_type": "speed",
            "season_elo": 1500.0,
            "career_elo": 1500.0,
            "event_count": 0,
            "pa_count": 0,
        }
        for r in reset_records
    ]
    for i in range(0, len(reset_batch), 500):
        client.table("talent_player_current").upsert(
            reset_batch[i:i + 500],
            on_conflict="player_id,talent_type,player_role"
        ).execute()
    logger.info(f"  Reset {len(reset_batch)} players to 1500")


def run_backfill(client, seasons: list[int], dry_run: bool,
                 start_date: str | None = None, end_date: str | None = None):
    dates = get_game_dates(client, seasons, start_date=start_date, end_date=end_date)
    if not dates:
        logger.info("No game dates found for the given range")
        return

    logger.info(f"Processing {len(dates)} dates across seasons {seasons}: {dates[0]} → {dates[-1]}")

    known_ids = get_known_player_ids(client)
    logger.info(f"Loaded {len(known_ids)} known player IDs")

    # In-memory state: {player_id: [elo, event_count]}
    player_state: dict[int, list] = {}
    player_last_season: dict[int, int] = {}   # last season each player was active
    loop_season: int = seasons[0]
    season_sb: dict[int, int] = {}            # SB counts accumulating for loop_season
    prev_season_sb: dict[int, int] = {}       # SB counts from the completed season

    total_sb = total_cs = total_3b = 0

    for date_str in dates:
        target = date.fromisoformat(date_str)
        season_year = int(date_str[:4])

        if season_year != loop_season:
            prev_season_sb = season_sb.copy()
            season_sb = {}
            loop_season = season_year
            logger.info(f"  Season boundary → {season_year} (prev season SB tracked for {len(prev_season_sb)} players)")
        pa_records = []
        detail_records = []
        ohlc_by_player: dict[int, dict] = {}
        seq_counter: dict[int, int] = {}  # game_pk → next seq

        # ── Statcast speed events (3B) ───────────────────────────────────────
        sc_events = get_statcast_speed_events(client, date_str)
        for ev in sc_events:
            pid = ev["batter_id"]
            if pid not in known_ids:
                continue
            if pid not in player_state:
                player_state[pid] = [1500.0, 0]
                player_last_season[pid] = season_year
            elif player_last_season.get(pid) != season_year:
                reset_elo = 1550.0 if prev_season_sb.get(pid, 0) > 25 else 1500.0
                player_state[pid] = [reset_elo, 0]
                player_last_season[pid] = season_year
            elo, cnt = player_state[pid]
            d = _delta(ev["speed_type"], cnt)
            if d == 0:
                continue

            if ev["speed_type"] == "Triple":
                total_3b += 1

            detail_records.append({
                "pa_id": ev["pa_id"],
                "player_id": pid,
                "player_role": "batter",
                "talent_type": "speed",
                "elo_before": round(elo, 4),
                "elo_after": round(elo + d, 4),
            })
            elo += d
            player_state[pid] = [elo, cnt + 1]

            if pid not in ohlc_by_player:
                ohlc_by_player[pid] = {"open": elo - d, "high": elo - d, "low": elo - d, "close": elo - d}
            ohlc_by_player[pid]["high"] = max(ohlc_by_player[pid]["high"], elo)
            ohlc_by_player[pid]["low"] = min(ohlc_by_player[pid]["low"], elo)
            ohlc_by_player[pid]["close"] = elo

        # ── MLB API SB/CS events ──────────────────────────────────────────────
        mlb_events = fetch_speed_events_for_date(target)
        for ev in mlb_events:
            pid = ev["player_id"]
            if pid not in known_ids:
                continue
            if pid not in player_state:
                player_state[pid] = [1500.0, 0]
                player_last_season[pid] = season_year
            elif player_last_season.get(pid) != season_year:
                reset_elo = 1550.0 if prev_season_sb.get(pid, 0) > 25 else 1500.0
                player_state[pid] = [reset_elo, 0]
                player_last_season[pid] = season_year
            elo, cnt = player_state[pid]
            game_pk = ev["game_pk"]

            if pid not in ohlc_by_player:
                ohlc_by_player[pid] = {"open": elo, "high": elo, "low": elo, "close": elo}
            open_elo = ohlc_by_player[pid]["open"]

            for _ in range(ev["sb"]):
                d = _delta("SB", cnt)
                seq = seq_counter.get(game_pk, 0)
                seq_counter[game_pk] = seq + 1
                pa_id = _synthetic_pa_id(game_pk, seq)
                pa_records.append({
                    "pa_id": pa_id, "game_pk": game_pk, "game_date": date_str,
                    "season_year": season_year, "batter_id": pid, "pitcher_id": pid,
                    "result_type": "SB", "inning": 0, "inning_half": "Top",
                    "at_bat_number": seq, "outs_when_up": 0,
                    "on_1b": True, "on_2b": False, "on_3b": False,
                    "home_team": ev["home_team"], "away_team": ev["away_team"],
                    "bat_score": 0, "fld_score": 0, "runner_id": pid,
                })
                detail_records.append({
                    "pa_id": pa_id, "player_id": pid, "player_role": "batter",
                    "talent_type": "speed",
                    "elo_before": round(elo, 4), "elo_after": round(elo + d, 4),
                })
                elo += d
                cnt += 1
                total_sb += 1
                season_sb[pid] = season_sb.get(pid, 0) + 1
                ohlc_by_player[pid]["high"] = max(ohlc_by_player[pid]["high"], elo)
                ohlc_by_player[pid]["low"] = min(ohlc_by_player[pid]["low"], elo)
                ohlc_by_player[pid]["close"] = elo

            for _ in range(ev["cs"]):
                d = _delta("CS", cnt)
                seq = seq_counter.get(game_pk, 0)
                seq_counter[game_pk] = seq + 1
                pa_id = _synthetic_pa_id(game_pk, seq)
                pa_records.append({
                    "pa_id": pa_id, "game_pk": game_pk, "game_date": date_str,
                    "season_year": season_year, "batter_id": pid, "pitcher_id": pid,
                    "result_type": "CS", "inning": 0, "inning_half": "Top",
                    "at_bat_number": seq, "outs_when_up": 0,
                    "on_1b": True, "on_2b": False, "on_3b": False,
                    "home_team": ev["home_team"], "away_team": ev["away_team"],
                    "bat_score": 0, "fld_score": 0, "runner_id": pid,
                })
                detail_records.append({
                    "pa_id": pa_id, "player_id": pid, "player_role": "batter",
                    "talent_type": "speed",
                    "elo_before": round(elo, 4), "elo_after": round(elo + d, 4),
                })
                elo += d
                cnt += 1
                total_cs += 1
                ohlc_by_player[pid]["high"] = max(ohlc_by_player[pid]["high"], elo)
                ohlc_by_player[pid]["low"] = min(ohlc_by_player[pid]["low"], elo)
                ohlc_by_player[pid]["close"] = elo

            player_state[pid] = [elo, cnt]

        # ── Write to DB ───────────────────────────────────────────────────────
        if not dry_run:
            batch = 500
            for i in range(0, len(pa_records), batch):
                client.table("plate_appearances").upsert(pa_records[i:i + batch]).execute()
            for i in range(0, len(detail_records), batch):
                client.table("talent_pa_detail").upsert(
                    detail_records[i:i + batch],
                    on_conflict="pa_id,player_id,talent_type"
                ).execute()
            ohlc_records = [
                {
                    "player_id": pid,
                    "game_date": date_str,
                    "talent_type": "speed",
                    "elo_type": "SEASON",
                    "open_elo": round(o["open"], 4),
                    "high_elo": round(o["high"], 4),
                    "low_elo": round(o["low"], 4),
                    "close_elo": round(o["close"], 4),
                    "total_pa": player_state.get(pid, [0, 0])[1],
                }
                for pid, o in ohlc_by_player.items()
            ]
            for i in range(0, len(ohlc_records), batch):
                client.table("talent_daily_ohlc").upsert(
                    ohlc_records[i:i + batch],
                    on_conflict="player_id,game_date,talent_type,elo_type"
                ).execute()

        sc_count = len(sc_events)
        mlb_count = len(mlb_events)
        logger.info(
            f"  {date_str}: {sc_count} Statcast events, {mlb_count} MLB API player-games"
            + (" [DRY RUN]" if dry_run else "")
        )

    # Players active in a prior season but absent from the current season were
    # never reset by the per-date boundary check. Apply the reset now so
    # talent_player_current reflects the correct current-season starting ELO.
    for pid in list(player_state.keys()):
        if player_last_season.get(pid) != loop_season:
            reset_elo = 1550.0 if prev_season_sb.get(pid, 0) > 25 else 1500.0
            player_state[pid] = [reset_elo, 0]

    # ── Final talent_player_current update ───────────────────────────────────
    if not dry_run and player_state:
        current_records = [
            {
                "player_id": pid,
                "player_role": "batter",
                "talent_type": "speed",
                "season_elo": round(state[0], 4),
                "career_elo": round(state[0], 4),
                "event_count": state[1],
                "pa_count": state[1],
            }
            for pid, state in player_state.items()
        ]
        for i in range(0, len(current_records), 500):
            client.table("talent_player_current").upsert(
                current_records[i:i + 500],
                on_conflict="player_id,talent_type,player_role"
            ).execute()
        logger.info(f"  Updated talent_player_current for {len(current_records)} players")

    logger.info(
        f"\nBackfill complete: {total_sb} SB, {total_cs} CS, {total_3b} 3B"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=None,
                        help="Single season shorthand (e.g. 2025). Ignored if --start-date/--end-date span multiple years.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD inclusive")
    parser.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD inclusive")
    args = parser.parse_args()

    # Derive the list of seasons to reset/backfill
    if args.start_date and args.end_date:
        start_year = int(args.start_date[:4])
        end_year = int(args.end_date[:4])
        seasons = list(range(start_year, end_year + 1))
    elif args.season:
        seasons = [args.season]
    else:
        import datetime
        seasons = [datetime.date.today().year]

    client = get_supabase()

    if not args.dry_run:
        reset_speed_data(client, seasons)

    run_backfill(client, seasons, args.dry_run,
                 start_date=args.start_date, end_date=args.end_date)


if __name__ == "__main__":
    main()
