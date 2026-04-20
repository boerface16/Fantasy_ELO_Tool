"""Talent endpoints — ports of frontend/src/api/talent.ts Supabase queries."""

from fastapi import APIRouter, Query
from src.api.deps import get_supabase

router = APIRouter()


@router.get("/players/{player_id}/radar")
async def player_talent_radar(player_id: int):
    sb = get_supabase()
    resp = sb.rpc("get_player_talent_radar", {"p_player_id": player_id}).execute()

    dimensions = []
    for row in (resp.data or []):
        dimensions.append({
            "talentType": row["talent_type"],
            "playerRole": row["player_role"],
            "seasonElo": row["season_elo"],
            "careerElo": row["career_elo"],
            "seasonRank": row.get("season_rank"),
            "careerRank": row.get("career_rank"),
            "totalPlayers": row.get("total_in_role"),
        })

    return {"playerId": player_id, "dimensions": dimensions}


@router.get("/players/{player_id}/ohlc")
async def player_talent_ohlc(player_id: int, talent_type: str = Query(...), season: int = None):
    sb = get_supabase()
    query = (
        sb.table("talent_daily_ohlc")
        .select("game_date, open_elo, high_elo, low_elo, close_elo, total_pa, talent_type")
        .eq("player_id", player_id)
        .eq("talent_type", talent_type)
        .eq("elo_type", "SEASON")
        .order("game_date")
    )
    if season is not None:
        query = query.gte("game_date", f"{season}-01-01").lt("game_date", f"{season + 1}-01-01")
    resp = query.execute()
    ohlc_by_date = {r["game_date"]: r for r in resp.data or []}

    # Build date spine from daily_ohlc (one row per game day the player appeared).
    # This covers both BATTING and PITCHING roles — use whichever has data.
    spine_query = (
        sb.table("daily_ohlc")
        .select("game_date")
        .eq("player_id", player_id)
        .eq("elo_type", "SEASON")
        .order("game_date")
    )
    if season is not None:
        spine_query = spine_query.gte("game_date", f"{season}-01-01").lt("game_date", f"{season + 1}-01-01")
    spine_dates = [r["game_date"] for r in spine_query.execute().data or []]

    # Deduplicate dates (player may have both BATTING and PITCHING rows on same day)
    spine_dates = sorted(set(spine_dates))

    if not spine_dates:
        # No game-day spine — return raw rows only
        return [
            {
                "game_date": r["game_date"],
                "open":     r["open_elo"],
                "high":     r["high_elo"],
                "low":      r["low_elo"],
                "close":    r["close_elo"],
                "delta":    r["close_elo"] - r["open_elo"],
                "total_pa": r["total_pa"],
                "role":     talent_type,
            }
            for r in resp.data or []
        ]

    # Forward-fill: emit flat candle on game days with no talent event
    result = []
    last_close = 1500.0
    for gd in spine_dates:
        if gd in ohlc_by_date:
            r = ohlc_by_date[gd]
            result.append({
                "game_date": gd,
                "open":     r["open_elo"],
                "high":     r["high_elo"],
                "low":      r["low_elo"],
                "close":    r["close_elo"],
                "delta":    r["close_elo"] - r["open_elo"],
                "total_pa": r["total_pa"],
                "role":     talent_type,
            })
            last_close = r["close_elo"]
        else:
            result.append({
                "game_date": gd,
                "open":     last_close,
                "high":     last_close,
                "low":      last_close,
                "close":    last_close,
                "delta":    0.0,
                "total_pa": 0,
                "role":     talent_type,
            })
    return result


@router.get("/leaderboard")
async def talent_leaderboard(
    talent_type: str = Query(..., alias="type"),
    player_role: str = Query(..., alias="role"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    min_pa: int = Query(None, ge=0),
    team: str = Query(None),
    days: int = Query(None, ge=1, le=365),
    from_date: str = Query(None),
):
    if min_pa is None:
        min_pa = 5 if talent_type == "speed" else 20
    sb = get_supabase()
    offset = (page - 1) * limit

    if days is not None or from_date is not None:
        from datetime import datetime, timedelta
        from collections import defaultdict
        if days is not None:
            start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        else:
            start_date = from_date

        query = (
            sb.table("talent_daily_ohlc")
            .select("player_id, open_elo, close_elo, total_pa, players!inner(full_name, team, position)")
            .gte("game_date", start_date)
            .eq("talent_type", talent_type)
            .limit(10000)
        )
        if team:
            query = query.eq("players.team", team)
        resp = query.execute()

        agg: dict = defaultdict(lambda: {"elo_delta": 0.0, "pa_count": 0})
        player_info: dict = {}
        for row in resp.data or []:
            pid = row["player_id"]
            agg[pid]["elo_delta"] += (row["close_elo"] or 0.0) - (row["open_elo"] or 0.0)
            agg[pid]["pa_count"] += row.get("total_pa") or 0
            player_info[pid] = row["players"]

        sorted_results = sorted(agg.items(), key=lambda x: x[1]["elo_delta"], reverse=True)
        page_slice = sorted_results[offset: offset + limit]
        return [
            {
                "player_id": pid,
                "season_elo": None,
                "career_elo": None,
                "elo_delta": round(data["elo_delta"], 1),
                "pa_count": data["pa_count"],
                "full_name": player_info[pid]["full_name"],
                "team": player_info[pid]["team"],
                "position": player_info[pid]["position"],
            }
            for pid, data in page_slice
        ]

    query = (
        sb.table("talent_player_current")
        .select("player_id, season_elo, career_elo, pa_count, players!inner(full_name, team, position)")
        .eq("talent_type", talent_type)
        .eq("player_role", player_role)
        .gte("pa_count", min_pa)
        .not_.is_("season_elo", "null")
        .order("season_elo", desc=True)
        .range(offset, offset + limit - 1)
    )
    if team:
        query = query.eq("players.team", team)
    resp = query.execute()

    return [
        {
            "player_id": row["player_id"],
            "season_elo": row["season_elo"],
            "career_elo": row["career_elo"],
            "pa_count": row["pa_count"],
            "full_name": row["players"]["full_name"],
            "team": row["players"]["team"],
            "position": row["players"]["position"],
        }
        for row in (resp.data or [])
    ]
