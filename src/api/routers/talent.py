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


@router.get("/leaderboard")
async def talent_leaderboard(
    talent_type: str = Query(..., alias="type"),
    player_role: str = Query(..., alias="role"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    sb = get_supabase()
    offset = (page - 1) * limit

    resp = (
        sb.table("talent_player_current")
        .select("player_id, season_elo, career_elo, pa_count, players!inner(full_name, team, position)")
        .eq("talent_type", talent_type)
        .eq("player_role", player_role)
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
