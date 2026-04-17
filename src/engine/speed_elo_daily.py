"""Daily speed ELO update using MLB API box scores.

Supplements talent_batch's Statcast-based processing (which handles 3B)
with SB/CS events from MLB API box scores, since Statcast pitch data
omits stolen base events.

For each player with SB/CS on a date, checks what's already been recorded
in plate_appearances (by talent_batch) and applies only the missing deltas.
"""

import logging
from datetime import date

from src.engine.multi_elo_config import MultiEloConfig
from src.engine.multi_elo_engine import MultiEloEngine
from src.etl.fetch_mlb_box_scores import fetch_speed_events_for_date

logger = logging.getLogger(__name__)

_config = MultiEloConfig()
_engine = MultiEloEngine(config=_config)

K_SPEED = _config.get_batter_k_factor("speed")
SCALE_SPEED = _config.get_batter_scale("speed")

# Weights from multi_elo_config.yaml baserunning_weights
_BR_WEIGHTS = {
    "SB":  _config.get_baserunning_weights("SB")["speed"],   # +1.0
    "CS":  _config.get_baserunning_weights("CS")["speed"],   # -1.5
    "PKO": _config.get_baserunning_weights("PKO")["speed"],  # -0.5
}


def _speed_delta(result_type: str, event_count: int) -> float:
    """Compute speed ELO delta for one SB/CS/PKO event."""
    weight = _BR_WEIGHTS[result_type]
    reliability = _engine.calculate_reliability(event_count, "speed")
    actual = 1.0 if weight > 0 else 0.0
    return K_SPEED * SCALE_SPEED * abs(weight) * (actual - 0.5) * reliability


def _load_player_speed_state(client, player_id: int) -> tuple[float, int]:
    """Return (season_elo, event_count) for a player's speed dimension."""
    rows = (
        client.table("talent_player_current")
        .select("season_elo,event_count")
        .eq("player_id", player_id)
        .eq("talent_type", "speed")
        .eq("player_role", "batter")
        .execute()
        .data
    )
    if rows:
        return float(rows[0]["season_elo"]), int(rows[0]["event_count"])
    return 1500.0, 0


def _count_recorded_sb_cs(client, player_id: int, date_str: str) -> tuple[int, int]:
    """Count SB and CS events already in plate_appearances for this player+date.

    Covers Statcast rows written by the daily pipeline (unlikely but possible).
    """
    rows = (
        client.table("plate_appearances")
        .select("result_type")
        .eq("game_date", date_str)
        .eq("runner_id", player_id)
        .in_("result_type", ["SB", "CS", "PKO"])
        .execute()
        .data
    ) or []
    sb_count = sum(1 for r in rows if r["result_type"] == "SB")
    cs_count = sum(1 for r in rows if r["result_type"] in ("CS", "PKO"))
    return sb_count, cs_count


def _synthetic_pa_id(game_pk: int, player_id: int, seq: int) -> int:
    """Synthetic pa_id for MLB API supplement rows.

    Uses game_pk * 1_000_000 + 950_000 + seq. Safe from collision:
    - Regular PAs: game_pk * 1000 + at_bat_number (~max 60k per game)
    - Statcast baserunning: game_pk * 1_000_000 + at_bat_number*1000 (~max 60k)
    - Synthetic: game_pk * 1_000_000 + 950_000 + seq (seq < 50)
    """
    return game_pk * 1_000_000 + 950_000 + seq


def run_speed_elo_for_date(target_date: date, client) -> dict:
    """Apply SB/CS speed ELO events for target_date using MLB API box scores.

    Only applies events not already in plate_appearances (deduplication).
    Writes synthetic plate_appearances, talent_pa_detail, talent_player_current,
    and talent_daily_ohlc rows.

    Returns summary dict: {players_updated, sb_applied, cs_applied}.
    """
    date_str = target_date.isoformat()
    season = target_date.year

    mlb_events = fetch_speed_events_for_date(target_date)
    if not mlb_events:
        logger.info(f"  Speed ELO: no SB/CS events on {date_str}")
        return {"players_updated": 0, "sb_applied": 0, "cs_applied": 0}

    # Confirm these players are in our DB (skip unknowns to avoid FK violations)
    all_pids = list({e["player_id"] for e in mlb_events})
    known: set[int] = set()
    for i in range(0, len(all_pids), 100):
        rows = (
            client.table("players")
            .select("player_id")
            .in_("player_id", all_pids[i:i + 100])
            .execute()
            .data
        ) or []
        known.update(r["player_id"] for r in rows)

    pa_records = []
    detail_records = []
    current_records = []
    ohlc_records = []

    players_updated = sb_applied = cs_applied = 0
    seq_counter: dict[int, int] = {}  # game_pk → next seq

    for ev in mlb_events:
        pid = ev["player_id"]
        if pid not in known:
            continue

        game_pk = ev["game_pk"]
        mlb_sb = ev["sb"]
        mlb_cs = ev["cs"]

        recorded_sb, recorded_cs = _count_recorded_sb_cs(client, pid, date_str)
        missing_sb = max(0, mlb_sb - recorded_sb)
        missing_cs = max(0, mlb_cs - recorded_cs)

        if missing_sb == 0 and missing_cs == 0:
            continue

        elo, event_count = _load_player_speed_state(client, pid)
        open_elo = elo
        any_applied = False

        # Apply SBs
        for _ in range(missing_sb):
            delta = _speed_delta("SB", event_count)
            seq = seq_counter.get(game_pk, 0)
            seq_counter[game_pk] = seq + 1
            pa_id = _synthetic_pa_id(game_pk, pid, seq)

            pa_records.append({
                "pa_id": pa_id,
                "game_pk": game_pk,
                "game_date": date_str,
                "season_year": season,
                "batter_id": pid,
                "pitcher_id": pid,
                "result_type": "SB",
                "inning": 0,
                "inning_half": "Top",
                "at_bat_number": seq,
                "outs_when_up": 0,
                "on_1b": True,
                "on_2b": False,
                "on_3b": False,
                "home_team": ev["home_team"],
                "away_team": ev["away_team"],
                "bat_score": 0,
                "fld_score": 0,
                "runner_id": pid,
            })
            detail_records.append({
                "pa_id": pa_id,
                "player_id": pid,
                "player_role": "batter",
                "talent_type": "speed",
                "elo_before": round(elo, 4),
                "elo_after": round(elo + delta, 4),
            })
            elo += delta
            event_count += 1
            sb_applied += 1
            any_applied = True

        # Apply CSs
        for _ in range(missing_cs):
            delta = _speed_delta("CS", event_count)
            seq = seq_counter.get(game_pk, 0)
            seq_counter[game_pk] = seq + 1
            pa_id = _synthetic_pa_id(game_pk, pid, seq)

            pa_records.append({
                "pa_id": pa_id,
                "game_pk": game_pk,
                "game_date": date_str,
                "season_year": season,
                "batter_id": pid,
                "pitcher_id": pid,
                "result_type": "CS",
                "inning": 0,
                "inning_half": "Top",
                "at_bat_number": seq,
                "outs_when_up": 0,
                "on_1b": True,
                "on_2b": False,
                "on_3b": False,
                "home_team": ev["home_team"],
                "away_team": ev["away_team"],
                "bat_score": 0,
                "fld_score": 0,
                "runner_id": pid,
            })
            detail_records.append({
                "pa_id": pa_id,
                "player_id": pid,
                "player_role": "batter",
                "talent_type": "speed",
                "elo_before": round(elo, 4),
                "elo_after": round(elo + delta, 4),
            })
            elo += delta
            event_count += 1
            cs_applied += 1
            any_applied = True

        if any_applied:
            current_records.append({
                "player_id": pid,
                "player_role": "batter",
                "talent_type": "speed",
                "season_elo": round(elo, 4),
                "career_elo": round(elo, 4),
                "event_count": event_count,
                "pa_count": event_count,
            })
            ohlc_records.append({
                "player_id": pid,
                "game_date": date_str,
                "talent_type": "speed",
                "elo_type": "SEASON",
                "open_elo": round(open_elo, 4),
                "high_elo": round(max(open_elo, elo), 4),
                "low_elo": round(min(open_elo, elo), 4),
                "close_elo": round(elo, 4),
                "total_pa": event_count,
            })
            players_updated += 1

    # Upload in batches
    batch_size = 500
    for i in range(0, len(pa_records), batch_size):
        client.table("plate_appearances").upsert(
            pa_records[i:i + batch_size]
        ).execute()

    for i in range(0, len(detail_records), batch_size):
        client.table("talent_pa_detail").upsert(
            detail_records[i:i + batch_size],
            on_conflict="pa_id,player_id,talent_type"
        ).execute()

    for i in range(0, len(current_records), batch_size):
        client.table("talent_player_current").upsert(
            current_records[i:i + batch_size],
            on_conflict="player_id,talent_type,player_role"
        ).execute()

    for i in range(0, len(ohlc_records), batch_size):
        client.table("talent_daily_ohlc").upsert(
            ohlc_records[i:i + batch_size],
            on_conflict="player_id,game_date,talent_type,elo_type"
        ).execute()

    logger.info(
        f"  Speed ELO supplement {date_str}: "
        f"{players_updated} players, +{sb_applied} SB, -{cs_applied} CS"
    )
    return {
        "players_updated": players_updated,
        "sb_applied": sb_applied,
        "cs_applied": cs_applied,
    }
