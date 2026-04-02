"""Fast bulk loader for 2025 Statcast data + ELO computation.

Fetches Statcast in monthly chunks, uploads via psycopg2 (not REST API),
and processes ELO/talent in bulk. ~2-3 minutes vs 60+ minutes day-by-day.

Usage:
    python -m scripts.bulk_load
    python -m scripts.bulk_load --end-date 2026-04-02 #year month day
"""

import argparse
import logging
import math
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pybaseball import statcast
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.etl.statcast_to_pa import convert_statcast_to_pa
from src.etl.player_registry import fetch_player_from_mlb_api
from src.engine.elo_batch import EloBatch
from src.engine.elo_calculator import PlayerEloState
from src.engine.elo_config import INITIAL_ELO
from src.engine.re24_baseline import RE24Baseline
from src.engine.park_factor import ParkFactor
from src.engine.talent_batch import TalentBatch
from src.pipeline.daily_pipeline import load_current_elo_states, load_current_talent_states
from src.etl.upload_to_supabase import get_supabase_client, prepare_pa_records


def get_db_conn():
    """Connect via psycopg2, handling passwords with @ in them."""
    db_url = os.environ["DATABASE_URL"]
    prefix, hostpart = db_url.rsplit("@", 1)
    creds = prefix.replace("postgresql://", "").replace("postgres://", "")
    user, password = creds.split(":", 1)
    host_port, dbname = hostpart.rsplit("/", 1)
    host, port = host_port.rsplit(":", 1)
    return psycopg2.connect(host=host, port=int(port), user=user, password=password, dbname=dbname)


# Known regular-season opening days per year (used when DB is empty in --fresh mode)
SEASON_STARTS = {
    2025: date(2025, 3, 27),
    2026: date(2026, 3, 18),
}


def get_season_start(year: int) -> date:
    return SEASON_STARTS.get(year, date(year, 3, 20))


def get_resume_date(conn) -> date:
    """Find the day after the latest plate_appearances date."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(game_date) FROM plate_appearances;")
    result = cur.fetchone()[0]
    cur.close()
    if result:
        return result + timedelta(days=1)
    return date(2025, 3, 27)  # season start


def load_pas_from_db(conn, start: date, end: date) -> pd.DataFrame:
    """Load plate appearances from DB for a date range (used by --fresh recompute)."""
    logger.info(f"Loading plate appearances from DB: {start} → {end}")
    cur = conn.cursor()
    cur.execute("""
        SELECT pa_id, game_pk, game_date, batter_id, pitcher_id,
               result_type, delta_run_exp, xwoba,
               on_1b, on_2b, on_3b, outs_when_up, home_team, away_team
        FROM plate_appearances
        WHERE game_date BETWEEN %s AND %s
        ORDER BY game_date, pa_id
    """, (start.isoformat(), end.isoformat()))
    rows = cur.fetchall()
    cur.close()
    cols = [
        'pa_id', 'game_pk', 'game_date', 'batter_id', 'pitcher_id',
        'result_type', 'delta_run_exp', 'xwoba',
        'on_1b', 'on_2b', 'on_3b', 'outs_when_up', 'home_team', 'away_team',
    ]
    df = pd.DataFrame(rows, columns=cols)
    logger.info(f"  Loaded {len(df):,} plate appearances from DB")
    return df


def fetch_monthly_chunks(start: date, end: date) -> pd.DataFrame:
    """Fetch Statcast data in monthly chunks, return combined DataFrame."""
    all_dfs = []
    current = start

    while current <= end:
        month_end = min(
            date(current.year, current.month + 1, 1) - timedelta(days=1) if current.month < 12
            else date(current.year, 12, 31),
            end
        )
        logger.info(f"Fetching Statcast: {current} → {month_end}")
        df = statcast(start_dt=current.strftime("%Y-%m-%d"), end_dt=month_end.strftime("%Y-%m-%d"))

        if df is not None and not df.empty:
            if "game_type" in df.columns:
                df = df[df["game_type"] == "R"]
            logger.info(f"  {len(df):,} regular season pitches")
            all_dfs.append(df)
        else:
            logger.info(f"  No data")

        current = month_end + timedelta(days=1)

    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


def register_players_psycopg2(conn, pa_df):
    """Detect and register new players via psycopg2."""
    pa_ids = set()
    if "batter_id" in pa_df.columns:
        pa_ids.update(int(x) for x in pa_df["batter_id"].dropna().unique())
    if "pitcher_id" in pa_df.columns:
        pa_ids.update(int(x) for x in pa_df["pitcher_id"].dropna().unique())

    cur = conn.cursor()
    cur.execute("SELECT player_id FROM players;")
    existing = {row[0] for row in cur.fetchall()}
    new_ids = pa_ids - existing

    if not new_ids:
        logger.info("No new players to register")
        cur.close()
        return

    logger.info(f"Registering {len(new_ids)} new players via MLB API...")
    records = []
    for pid in sorted(new_ids):
        info = fetch_player_from_mlb_api(pid)
        if info:
            records.append(info)
        else:
            records.append({
                "player_id": pid, "first_name": "", "last_name": "",
                "full_name": f"Player {pid}", "team": "", "position": "",
            })

    if records:
        execute_values(
            cur,
            """INSERT INTO players (player_id, first_name, last_name, full_name, team, position)
               VALUES %s ON CONFLICT (player_id) DO NOTHING""",
            [(r["player_id"], r["first_name"], r["last_name"], r["full_name"], r["team"], r["position"])
             for r in records],
        )
        conn.commit()
    logger.info(f"  Registered {len(records)} players")
    cur.close()


def upload_pas_psycopg2(conn, pa_df):
    """Bulk upload plate_appearances via psycopg2."""
    records = prepare_pa_records(pa_df)
    if not records:
        return

    cols = [
        "pa_id", "game_pk", "game_date", "season_year", "batter_id", "pitcher_id",
        "result_type", "delta_run_exp", "xwoba", "launch_speed", "launch_angle",
        "at_bat_number", "inning", "inning_half", "outs_when_up",
        "on_1b", "on_2b", "on_3b", "bat_score", "fld_score", "home_team", "away_team",
    ]

    cur = conn.cursor()
    values = []
    for r in records:
        values.append(tuple(r.get(c) for c in cols))

    col_str = ", ".join(cols)
    execute_values(
        cur,
        f"INSERT INTO plate_appearances ({col_str}) VALUES %s ON CONFLICT (pa_id) DO NOTHING",
        values,
        page_size=1000,
    )
    conn.commit()
    logger.info(f"  Uploaded {len(records):,} plate appearances")
    cur.close()


def upload_player_elo_psycopg2(conn, batch: EloBatch):
    """Upload player_elo results via psycopg2."""
    records = batch.get_player_elo_records(active_only=True)
    if not records:
        return

    cur = conn.cursor()
    values = [
        (r["player_id"], r["batting_elo"], r["pitching_elo"], r["batting_pa"],
         r["pitching_pa"], r["composite_elo"], r["pa_count"], r["last_game_date"])
        for r in records
    ]
    execute_values(
        cur,
        """INSERT INTO player_elo (player_id, batting_elo, pitching_elo, batting_pa,
                                    pitching_pa, composite_elo, pa_count, last_game_date)
           VALUES %s
           ON CONFLICT (player_id) DO UPDATE SET
             batting_elo = EXCLUDED.batting_elo, pitching_elo = EXCLUDED.pitching_elo,
             batting_pa = EXCLUDED.batting_pa, pitching_pa = EXCLUDED.pitching_pa,
             composite_elo = EXCLUDED.composite_elo, pa_count = EXCLUDED.pa_count,
             last_game_date = EXCLUDED.last_game_date""",
        values,
        page_size=500,
    )
    conn.commit()
    logger.info(f"  Uploaded {len(records):,} player_elo records")
    cur.close()


def upload_daily_ohlc_psycopg2(conn, daily_ohlc):
    """Upload daily_ohlc via psycopg2."""
    cur = conn.cursor()
    values = [
        (int(o.player_id), o.game_date.isoformat(), o.elo_type,
         round(o.open_elo, 4), round(o.high_elo, 4), round(o.low_elo, 4), round(o.close_elo, 4),
         o.games_played, o.total_pa, o.role)
        for o in daily_ohlc
    ]
    execute_values(
        cur,
        """INSERT INTO daily_ohlc (player_id, game_date, elo_type, open, high, low, close,
                                    games_played, total_pa, role)
           VALUES %s
           ON CONFLICT (player_id, game_date, elo_type, role) DO UPDATE SET
             open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
             close = EXCLUDED.close, games_played = EXCLUDED.games_played, total_pa = EXCLUDED.total_pa""",
        values,
        page_size=500,
    )
    conn.commit()
    logger.info(f"  Uploaded {len(values):,} daily_ohlc records")
    cur.close()


def upload_talent_player_psycopg2(conn, talent_batch: TalentBatch):
    """Upload talent_player_current via psycopg2."""
    records = talent_batch.get_talent_player_records(active_only=True)
    if not records:
        return

    cur = conn.cursor()
    values = [
        (r["player_id"], r["player_role"], r["talent_type"],
         r["season_elo"], r["career_elo"], r["event_count"], r["pa_count"])
        for r in records
    ]
    execute_values(
        cur,
        """INSERT INTO talent_player_current (player_id, player_role, talent_type,
                                               season_elo, career_elo, event_count, pa_count)
           VALUES %s
           ON CONFLICT (player_id, talent_type, player_role) DO UPDATE SET
             season_elo = EXCLUDED.season_elo, career_elo = EXCLUDED.career_elo,
             event_count = EXCLUDED.event_count, pa_count = EXCLUDED.pa_count""",
        values,
        page_size=500,
    )
    conn.commit()
    logger.info(f"  Uploaded {len(records):,} talent_player_current records")
    cur.close()


def upload_talent_ohlc_psycopg2(conn, talent_ohlc):
    """Upload talent_daily_ohlc via psycopg2."""
    cur = conn.cursor()
    values = [
        (int(o["player_id"]), o["game_date"], o["talent_type"],
         o.get("elo_type", "SEASON"),
         round(float(o["open"]), 4), round(float(o["high"]), 4),
         round(float(o["low"]), 4), round(float(o["close"]), 4),
         int(o.get("total_pa", 0)))
        for o in talent_ohlc
    ]
    execute_values(
        cur,
        """INSERT INTO talent_daily_ohlc (player_id, game_date, talent_type, elo_type,
                                           open_elo, high_elo, low_elo, close_elo, total_pa)
           VALUES %s
           ON CONFLICT (player_id, game_date, talent_type, elo_type) DO UPDATE SET
             open_elo = EXCLUDED.open_elo, high_elo = EXCLUDED.high_elo,
             low_elo = EXCLUDED.low_elo, close_elo = EXCLUDED.close_elo,
             total_pa = EXCLUDED.total_pa""",
        values,
        page_size=500,
    )
    conn.commit()
    logger.info(f"  Uploaded {len(values):,} talent_daily_ohlc records")
    cur.close()


def _build_season_projections() -> dict[int, tuple[float | None, float | None]]:
    """Fetch FanGraphs projections and build {player_id: (proj_batting, proj_pitching)} dict."""
    from src.engine.preseason_projections import (
        fetch_player_projections, projection_to_batter_elo, projection_to_pitcher_elo,
    )

    projections: dict[int, tuple[float | None, float | None]] = {}

    try:
        bat_df = fetch_player_projections("bat")
        if bat_df is not None:
            bat_elo = projection_to_batter_elo(bat_df)
            for pid, elo_arr in bat_elo.items():
                proj_batting = float(np.mean(elo_arr))
                projections[pid] = (proj_batting, projections.get(pid, (None, None))[1])
    except Exception as e:
        logger.warning(f"Failed to fetch batter projections: {e}")

    try:
        pit_df = fetch_player_projections("pit")
        if pit_df is not None:
            pit_elo = projection_to_pitcher_elo(pit_df)
            for pid, elo_arr in pit_elo.items():
                proj_pitching = float(np.mean(elo_arr))
                existing = projections.get(pid, (None, None))
                projections[pid] = (existing[0], proj_pitching)
    except Exception as e:
        logger.warning(f"Failed to fetch pitcher projections: {e}")

    logger.info(f"Built season projections for {len(projections)} players")
    return projections


def main():
    parser = argparse.ArgumentParser(description="Fast bulk data loader")
    parser.add_argument("--end-date", type=str, default="2025-09-28")
    parser.add_argument("--fresh", action="store_true",
                        help="Recompute all ELO from scratch (loads PAs from DB if they exist)")
    args = parser.parse_args()
    end = date.fromisoformat(args.end_date)

    conn = get_db_conn()
    logger.info("Connected to database")

    if args.fresh:
        # Check if PAs already exist in DB for this date range
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM plate_appearances WHERE game_date <= %s", (end,))
        existing_pa_count = cur.fetchone()[0]
        cur.close()

        if existing_pa_count > 0:
            # PAs already in DB — skip Statcast fetch, recompute ELO from existing data
            logger.info(f"Fresh mode: found {existing_pa_count:,} existing PAs — recomputing ELO from DB")
            season_start = get_season_start(end.year)
            pa_df = load_pas_from_db(conn, season_start, end)
        else:
            # DB is empty — fetch from Statcast normally
            logger.info("Fresh mode: DB empty — fetching from Statcast")
            season_start = get_season_start(end.year)
            raw_df = fetch_monthly_chunks(season_start, end)
            if raw_df.empty:
                logger.info("No Statcast data fetched")
                conn.close()
                return
            pa_df = convert_statcast_to_pa(raw_df)
            register_players_psycopg2(conn, pa_df)
            logger.info("Uploading plate appearances...")
            upload_pas_psycopg2(conn, pa_df)
    else:
        # Normal incremental mode
        resume = get_resume_date(conn)
        if resume > end:
            logger.info(f"Already loaded through {end}. Nothing to do.")
            conn.close()
            return
        logger.info(f"Resuming from {resume} through {end}")

        raw_df = fetch_monthly_chunks(resume, end)
        if raw_df.empty:
            logger.info("No Statcast data fetched")
            conn.close()
            return
        logger.info(f"Total pitches fetched: {len(raw_df):,}")

        logger.info("Converting pitches to plate appearances...")
        pa_df = convert_statcast_to_pa(raw_df)
        logger.info(f"Total PAs: {len(pa_df):,}")

        register_players_psycopg2(conn, pa_df)
        logger.info("Uploading plate appearances...")
        upload_pas_psycopg2(conn, pa_df)

    if pa_df.empty:
        logger.info("No plate appearances to process")
        conn.close()
        return

    logger.info(f"Processing {len(pa_df):,} plate appearances")

    # ELO engine
    sb_client = get_supabase_client()

    if args.fresh:
        initial_states = {}
    else:
        logger.info("Loading prior ELO states...")
        initial_states = load_current_elo_states(sb_client)

    logger.info("Fetching season projections for ELO resets...")
    season_projections = _build_season_projections()

    re24 = RE24Baseline()
    park = ParkFactor()
    batch = EloBatch(
        initial_states=initial_states, re24_baseline=re24, park_factor=park,
        season_projections=season_projections,
    )

    logger.info("Running ELO calculation...")
    batch.process(pa_df)
    logger.info(f"  {len(pa_df):,} PAs processed, {len(batch.daily_ohlc)} OHLC records")

    # Clear stale ELO data before uploading fresh results
    if args.fresh:
        logger.info("Fresh mode: clearing existing ELO data...")
        cur = conn.cursor()
        cur.execute("DELETE FROM daily_ohlc;")
        cur.execute("DELETE FROM player_elo;")
        conn.commit()
        cur.close()

    logger.info("Uploading player_elo...")
    upload_player_elo_psycopg2(conn, batch)
    logger.info("Uploading daily_ohlc...")
    upload_daily_ohlc_psycopg2(conn, batch.daily_ohlc)

    # Talent engine
    if args.fresh:
        initial_batters, initial_pitchers = {}, {}
    else:
        logger.info("Loading prior talent states...")
        initial_batters, initial_pitchers = load_current_talent_states(sb_client)

    talent_batch = TalentBatch(initial_batters=initial_batters, initial_pitchers=initial_pitchers)

    logger.info("Running talent ELO calculation...")
    talent_batch.process(pa_df)
    logger.info(f"  {len(talent_batch.talent_daily_ohlc)} talent OHLC records")

    if args.fresh:
        logger.info("Fresh mode: clearing existing talent data...")
        cur = conn.cursor()
        cur.execute("DELETE FROM talent_daily_ohlc;")
        cur.execute("DELETE FROM talent_player_current;")
        conn.commit()
        cur.close()

    logger.info("Uploading talent_player_current...")
    upload_talent_player_psycopg2(conn, talent_batch)
    logger.info("Uploading talent_daily_ohlc...")
    upload_talent_ohlc_psycopg2(conn, talent_batch.talent_daily_ohlc)

    # 10. Summary
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM plate_appearances;")
    total_pa = cur.fetchone()[0]
    cur.execute("SELECT max(game_date) FROM plate_appearances;")
    max_date = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM player_elo;")
    total_players = cur.fetchone()[0]
    cur.close()

    conn.close()

    print("\n" + "=" * 60)
    print("BULK LOAD COMPLETE")
    print("=" * 60)
    print(f"  Total PAs in DB: {total_pa:,}")
    print(f"  Latest date: {max_date}")
    print(f"  Players with ELO: {total_players:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
