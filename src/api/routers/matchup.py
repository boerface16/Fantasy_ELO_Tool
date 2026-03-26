"""Matchup endpoints — ports of frontend/src/api/matchup.ts Supabase queries."""

from fastapi import APIRouter
from src.api.deps import get_supabase
from src.fantasy.matchup_predictor import predict_plate_appearance

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


@router.get("/predict/{batter_id}/{pitcher_id}")
async def predict_matchup(batter_id: int, pitcher_id: int):
    """Server-side matchup prediction for batter vs pitcher."""
    sb = get_supabase()

    # Fetch batter talent
    batter_resp = (
        sb.table("talent_player_current")
        .select("talent_type, season_elo")
        .eq("player_id", batter_id)
        .eq("player_role", "batter")
        .in_("talent_type", ["contact", "power", "discipline"])
        .execute()
    )
    batter_elo = {r["talent_type"]: r["season_elo"] for r in (batter_resp.data or [])}
    batter = {
        "contact": batter_elo.get("contact", 1500),
        "power": batter_elo.get("power", 1500),
        "discipline": batter_elo.get("discipline", 1500),
    }

    # Fetch pitcher talent
    pitcher_resp = (
        sb.table("talent_player_current")
        .select("talent_type, season_elo")
        .eq("player_id", pitcher_id)
        .eq("player_role", "pitcher")
        .in_("talent_type", ["stuff", "bip_suppression", "command"])
        .execute()
    )
    pitcher_elo = {r["talent_type"]: r["season_elo"] for r in (pitcher_resp.data or [])}
    pitcher = {
        "stuff": pitcher_elo.get("stuff", 1500),
        "bip_suppression": pitcher_elo.get("bip_suppression", 1500),
        "command": pitcher_elo.get("command", 1500),
    }

    pred = predict_plate_appearance(batter, pitcher)

    return {
        "batterId": batter_id,
        "pitcherId": pitcher_id,
        "probabilities": {k: round(v, 4) for k, v in pred["probabilities"].items()},
        "expectedWoba": round(pred["expected_woba"], 3),
        "zDiffs": {k: round(v, 3) for k, v in pred["z_diffs"].items()},
        "stages": pred["stages"],
    }
