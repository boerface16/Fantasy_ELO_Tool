"""ELO endpoints — ports of frontend/src/api/elo.ts Supabase queries."""

from fastapi import APIRouter, Query
from src.api.deps import get_supabase

router = APIRouter()


@router.get("/hot-players")
async def hot_players(date: str):
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("player_id, game_date, open, high, low, close, delta, total_pa, players!inner(full_name, team, position)")
        .eq("game_date", date)
        .eq("elo_type", "SEASON")
        .order("delta", desc=True)
        .limit(10)
        .execute()
    )
    return [_flatten_ohlc_player(row) for row in resp.data]


@router.get("/cold-players")
async def cold_players(date: str):
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("player_id, game_date, open, high, low, close, delta, total_pa, players!inner(full_name, team, position)")
        .eq("game_date", date)
        .eq("elo_type", "SEASON")
        .order("delta", desc=False)
        .limit(10)
        .execute()
    )
    return [_flatten_ohlc_player(row) for row in resp.data]


@router.get("/leaderboard")
async def leaderboard(
    position: str = Query("batter"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    sb = get_supabase()
    offset = (page - 1) * limit

    sort_column = "pitching_elo" if position == "pitcher" else "batting_elo"
    pa_column = "pitching_pa" if position == "pitcher" else "batting_pa"

    resp = (
        sb.table("player_elo")
        .select("player_id, composite_elo, batting_elo, pitching_elo, pa_count, batting_pa, pitching_pa, last_game_date, players!inner(full_name, team, position)")
        .gt(pa_column, 0)
        .order(sort_column, desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [_flatten_leaderboard(row) for row in resp.data]


@router.get("/players/{player_id}")
async def player_elo(player_id: int):
    sb = get_supabase()
    resp = (
        sb.table("player_elo")
        .select("player_id, composite_elo, batting_elo, pitching_elo, pa_count, batting_pa, pitching_pa, last_game_date, players!inner(player_id, full_name, team, position)")
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    row = resp.data
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "composite_elo": row["composite_elo"],
        "batting_elo": row.get("batting_elo") or 1500,
        "pitching_elo": row.get("pitching_elo") or 1500,
        "pa_count": row["pa_count"],
        "batting_pa": row.get("batting_pa") or 0,
        "pitching_pa": row.get("pitching_pa") or 0,
        "last_game_date": row["last_game_date"],
        "player": {
            "player_id": p["player_id"],
            "full_name": p["full_name"],
            "team": p["team"],
            "position": p["position"],
        },
    }


@router.get("/players/{player_id}/ohlc")
async def player_ohlc(player_id: int, role: str = None):
    sb = get_supabase()
    query = (
        sb.table("daily_ohlc")
        .select("game_date, open, high, low, close, delta, total_pa, role")
        .eq("player_id", player_id)
        .eq("elo_type", "SEASON")
        .order("game_date")
    )
    if role:
        query = query.eq("role", role)

    resp = query.execute()
    return resp.data


@router.get("/players/{player_id}/stats")
async def player_stats(player_id: int, role: str = None):
    ohlc_data = (await player_ohlc(player_id, role))

    if not ohlc_data:
        return {
            "totalPa": 0,
            "avgDelta": 0,
            "highestElo": {"value": 1500, "date": ""},
            "lowestElo": {"value": 1500, "date": ""},
            "avgRange": 0,
        }

    total_pa = sum(d["total_pa"] for d in ohlc_data)
    avg_delta = sum(d["delta"] for d in ohlc_data) / len(ohlc_data)

    highest = {"value": float("-inf"), "date": ""}
    lowest = {"value": float("inf"), "date": ""}
    range_sum = 0.0

    for d in ohlc_data:
        if d["high"] > highest["value"]:
            highest = {"value": d["high"], "date": d["game_date"]}
        if d["low"] < lowest["value"]:
            lowest = {"value": d["low"], "date": d["game_date"]}
        range_sum += d["high"] - d["low"]

    return {
        "totalPa": total_pa,
        "avgDelta": avg_delta,
        "highestElo": highest,
        "lowestElo": lowest,
        "avgRange": range_sum / len(ohlc_data),
    }


@router.get("/search")
async def search_players(q: str = Query("", min_length=2)):
    sb = get_supabase()
    resp = (
        sb.table("players")
        .select("player_id, full_name, team, position, player_elo(batting_pa, pitching_pa)")
        .ilike("full_name", f"%{q}%")
        .limit(10)
        .execute()
    )
    results = []
    for row in resp.data:
        elo = row.get("player_elo")
        is_two_way = False
        if elo:
            is_two_way = (elo.get("batting_pa") or 0) > 0 and (elo.get("pitching_pa") or 0) > 0
        results.append({
            "player_id": row["player_id"],
            "full_name": row["full_name"],
            "team": row["team"],
            "position": row["position"],
            "is_two_way": is_two_way,
        })
    return results


@router.get("/league-summary")
async def league_summary():
    sb = get_supabase()
    resp = sb.table("player_elo").select("composite_elo").execute()
    players = resp.data or []
    count = len(players)
    avg_elo = round(sum(p["composite_elo"] for p in players) / count) if count else 1500
    elite_count = sum(1 for p in players if p["composite_elo"] >= 1800)
    return {
        "activePlayersCount": count,
        "averageElo": avg_elo,
        "eliteCount": elite_count,
    }


@router.get("/latest-date")
async def latest_date():
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=True)
        .limit(1)
        .execute()
    )
    date = resp.data[0]["game_date"] if resp.data else None
    return {"date": date}


@router.get("/season-meta")
async def season_meta():
    sb = get_supabase()
    earliest = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=False)
        .limit(1)
        .execute()
    )
    latest = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=True)
        .limit(1)
        .execute()
    )

    start_date = earliest.data[0]["game_date"] if earliest.data else ""
    end_date = latest.data[0]["game_date"] if latest.data else ""
    year = int(start_date[:4]) if start_date else 2025

    return {"year": year, "startDate": start_date, "endDate": end_date}


# --- Helpers ---

def _flatten_ohlc_player(row: dict) -> dict:
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "game_date": row["game_date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "delta": row["delta"],
        "total_pa": row["total_pa"],
        "full_name": p["full_name"],
        "team": p["team"],
        "position": p["position"],
    }


def _flatten_leaderboard(row: dict) -> dict:
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "composite_elo": row["composite_elo"],
        "batting_elo": row.get("batting_elo") or 1500,
        "pitching_elo": row.get("pitching_elo") or 1500,
        "pa_count": row["pa_count"],
        "batting_pa": row.get("batting_pa") or 0,
        "pitching_pa": row.get("pitching_pa") or 0,
        "last_game_date": row["last_game_date"],
        "full_name": p["full_name"],
        "team": p["team"],
        "position": p["position"],
    }
