"""Fantasy endpoints — team ELO ratings."""

from fastapi import APIRouter

from src.api.deps import get_supabase

router = APIRouter()


@router.get("/team-elo/all")
async def all_team_elos():
    """Current ELO for all 30 teams (latest record per team)."""
    sb = get_supabase()
    resp = (
        sb.table("team_elo")
        .select("team_code,game_date,game_pk,elo_after,opponent_code,result,run_diff")
        .order("game_date", desc=True)
        .limit(300)
        .execute()
    )

    # Deduplicate: keep first (most recent) per team_code
    seen = set()
    teams = []
    for row in resp.data or []:
        if row["team_code"] not in seen:
            seen.add(row["team_code"])
            teams.append({
                "teamCode": row["team_code"],
                "elo": row["elo_after"],
                "lastGameDate": row["game_date"],
                "lastOpponent": row["opponent_code"],
                "lastResult": row["result"],
                "lastRunDiff": row["run_diff"],
            })

    teams.sort(key=lambda t: t["elo"], reverse=True)
    return teams


@router.get("/team-elo/{team_code}")
async def team_elo(team_code: str):
    """Current ELO + recent 20-game trend for a specific team."""
    sb = get_supabase()
    resp = (
        sb.table("team_elo")
        .select("team_code,game_date,game_pk,elo_before,elo_after,opponent_code,result,run_diff")
        .eq("team_code", team_code.upper())
        .order("game_date", desc=True)
        .limit(20)
        .execute()
    )

    rows = resp.data or []
    if not rows:
        return {"teamCode": team_code.upper(), "currentElo": 1500.0, "trend": []}

    current = rows[0]
    trend = [
        {
            "date": r["game_date"],
            "eloBefore": r["elo_before"],
            "eloAfter": r["elo_after"],
            "opponent": r["opponent_code"],
            "result": r["result"],
            "runDiff": r["run_diff"],
        }
        for r in rows
    ]

    return {
        "teamCode": current["team_code"],
        "currentElo": current["elo_after"],
        "trend": trend,
    }
