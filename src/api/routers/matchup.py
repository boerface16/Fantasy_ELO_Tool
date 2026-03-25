"""Matchup endpoints — ports of frontend/src/api/matchup.ts Supabase queries."""

from fastapi import APIRouter
from src.api.deps import get_supabase

router = APIRouter()


@router.get("/batter/{player_id}/talent")
async def batter_talent_elo(player_id: int):
    sb = get_supabase()
    resp = (
        sb.table("talent_player_current")
        .select("player_id, talent_type, season_elo, players!inner(full_name, team)")
        .eq("player_id", player_id)
        .eq("player_role", "batter")
        .in_("talent_type", ["contact", "power", "discipline"])
        .execute()
    )

    rows = resp.data or []
    player = rows[0]["players"] if rows else {}
    elo_map = {row["talent_type"]: row["season_elo"] for row in rows}

    return {
        "playerId": player_id,
        "fullName": player.get("full_name", ""),
        "team": player.get("team", ""),
        "contact": elo_map.get("contact", 1500),
        "power": elo_map.get("power", 1500),
        "discipline": elo_map.get("discipline", 1500),
    }


@router.get("/pitcher/{player_id}/talent")
async def pitcher_talent_elo(player_id: int):
    sb = get_supabase()
    resp = (
        sb.table("talent_player_current")
        .select("player_id, talent_type, season_elo, players!inner(full_name, team)")
        .eq("player_id", player_id)
        .eq("player_role", "pitcher")
        .in_("talent_type", ["stuff", "bip_suppression", "command"])
        .execute()
    )

    rows = resp.data or []
    player = rows[0]["players"] if rows else {}
    elo_map = {row["talent_type"]: row["season_elo"] for row in rows}

    return {
        "playerId": player_id,
        "fullName": player.get("full_name", ""),
        "team": player.get("team", ""),
        "stuff": elo_map.get("stuff", 1500),
        "bipSuppression": elo_map.get("bip_suppression", 1500),
        "command": elo_map.get("command", 1500),
    }
