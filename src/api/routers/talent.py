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
    return [
        {
            "game_date": r["game_date"],
            "open":      r["open_elo"],
            "high":      r["high_elo"],
            "low":       r["low_elo"],
            "close":     r["close_elo"],
            "delta":     r["close_elo"] - r["open_elo"],
            "total_pa":  r["total_pa"],
            "role":      talent_type,
        }
        for r in resp.data or []
    ]


@router.get("/leaderboard")
async def talent_leaderboard(
    talent_type: str = Query(..., alias="type"),
    player_role: str = Query(..., alias="role"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    min_pa: int = Query(20, ge=0),
):
    sb = get_supabase()
    offset = (page - 1) * limit

    resp = (
        sb.table("talent_player_current")
        .select("player_id, season_elo, career_elo, pa_count, players!inner(full_name, team, position)")
        .eq("talent_type", talent_type)
        .eq("player_role", player_role)
        .gte("pa_count", min_pa)
        .not_.is_("season_elo", "null")
        .order("season_elo", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

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
