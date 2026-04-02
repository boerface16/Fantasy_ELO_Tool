"""Fantasy endpoints — team ELO, roster, schedule, projections."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.deps import get_supabase
from src.fantasy.roster_parser import parse_roster_text
from src.fantasy.schedule_fetcher import fetch_week_schedule
from src.fantasy.opponent_resolver import resolve_opponents
from src.fantasy.elo_lookup import EloLookup
from src.fantasy.matchup_predictor import predict_plate_appearance
from src.fantasy.fantasy_calculator import load_scoring_config, estimate_batter_points
from src.fantasy.weekly_projection import project_week

router = APIRouter()


class RosterRequest(BaseModel):
    roster_text: str


class WeeklyProjectionRequest(BaseModel):
    roster_text: str
    ref_date: str | None = None  # ISO date string, defaults to today


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


@router.get("/team-elo/{team_code}/history")
async def team_elo_history(team_code: str):
    """Full season ELO history for a team (all games)."""
    sb = get_supabase()
    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        resp = (
            sb.table("team_elo")
            .select("team_code,game_date,elo_before,elo_after,opponent_code,result,run_diff")
            .eq("team_code", team_code.upper())
            .order("game_date", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    return [
        {
            "date": r["game_date"],
            "eloBefore": r["elo_before"],
            "eloAfter": r["elo_after"],
            "opponent": r["opponent_code"],
            "result": r["result"],
            "runDiff": r["run_diff"],
        }
        for r in all_rows
    ]


@router.post("/roster")
async def parse_roster(req: RosterRequest):
    """Parse pasted roster text, return structured entries."""
    entries = parse_roster_text(req.roster_text)

    # Fuzzy-match names to DB players
    sb = get_supabase()
    matched = []
    for entry in entries:
        # Try exact name match first
        resp = (
            sb.table("players")
            .select("player_id, full_name, team, position")
            .ilike("full_name", f"%{entry.name}%")
            .limit(1)
            .execute()
        )
        player = resp.data[0] if resp.data else None

        matched.append({
            "slot": entry.slot,
            "name": entry.name,
            "team": entry.team,
            "playerId": player["player_id"] if player else None,
            "matchedName": player["full_name"] if player else None,
            "dbTeam": player["team"] if player else None,
            "position": player["position"] if player else None,
        })

    return {"entries": matched, "count": len(matched)}


@router.get("/schedule")
async def get_schedule(week: str | None = None):
    """Get MLB schedule for a given week (ISO date) or current week."""
    ref = date.fromisoformat(week) if week else date.today()
    games = fetch_week_schedule(ref)
    return {
        "games": [
            {
                "date": g.game_date.isoformat(),
                "gamePk": g.game_pk,
                "awayTeam": g.away_team,
                "homeTeam": g.home_team,
                "awayPitcher": g.away_pitcher_name,
                "awayPitcherId": g.away_pitcher_id,
                "homePitcher": g.home_pitcher_name,
                "homePitcherId": g.home_pitcher_id,
                "venue": g.venue,
            }
            for g in games
        ],
        "count": len(games),
    }


@router.post("/weekly-projection")
async def weekly_projection(req: WeeklyProjectionRequest):
    """Full weekly projection: roster + schedule → matchup grid + fantasy points."""
    roster = parse_roster_text(req.roster_text)
    ref = date.fromisoformat(req.ref_date) if req.ref_date else date.today()
    schedule = fetch_week_schedule(ref)

    sb = get_supabase()
    elo_lookup = EloLookup(sb)

    # Pre-load ELO for all pitcher IDs in schedule
    pitcher_ids = []
    for g in schedule:
        if g.away_pitcher_id:
            pitcher_ids.append(g.away_pitcher_id)
        if g.home_pitcher_id:
            pitcher_ids.append(g.home_pitcher_id)
    elo_lookup.load_batch(pitcher_ids)

    projection = project_week(roster, schedule, elo_lookup)

    return {
        "weekStart": projection.week_start.isoformat(),
        "weekEnd": projection.week_end.isoformat(),
        "totalPoints": round(projection.total_points, 1),
        "totalBatterPoints": round(projection.total_batter_points, 1),
        "totalPitcherPoints": round(projection.total_pitcher_points, 1),
        "batters": [
            {
                "name": b.player_name,
                "team": b.team,
                "slot": b.slot,
                "games": len(b.games),
                "totalPoints": round(b.total_points, 1),
                "pointsPerGame": round(b.points_per_game, 1),
                "matchups": [
                    {
                        "date": g.game_date.isoformat(),
                        "opponent": g.opponent_team,
                        "pitcher": g.opponent_pitcher_name,
                        "isHome": g.is_home,
                        "expectedWoba": round(g.expected_woba, 3),
                        "expectedPoints": round(g.expected_points, 1),
                    }
                    for g in b.games
                ],
            }
            for b in projection.batters
        ],
        "pitchers": [
            {
                "name": p.player_name,
                "team": p.team,
                "slot": p.slot,
                "starts": len(p.starts),
                "totalPoints": round(p.total_points, 1),
                "matchups": [
                    {
                        "date": s.game_date.isoformat(),
                        "opponent": s.opponent_team,
                        "isHome": s.is_home,
                        "expectedWoba": round(s.expected_woba, 3),
                        "expectedPoints": round(s.expected_points, 1),
                    }
                    for s in p.starts
                ],
            }
            for p in projection.pitchers
        ],
    }


@router.get("/matchup/{batter_id}/{pitcher_id}")
async def fantasy_matchup(batter_id: int, pitcher_id: int):
    """Single batter vs pitcher matchup with fantasy points."""
    sb = get_supabase()
    elo_lookup = EloLookup(sb)
    elo_lookup.load_batch([batter_id, pitcher_id])

    batter_elo = elo_lookup.get_batter_elo(batter_id)
    pitcher_elo = elo_lookup.get_pitcher_elo(pitcher_id)

    pred = predict_plate_appearance(batter_elo, pitcher_elo)
    scoring = load_scoring_config()
    pts = estimate_batter_points(pred["probabilities"], scoring, pas=4)

    return {
        "batterId": batter_id,
        "pitcherId": pitcher_id,
        "probabilities": {k: round(v, 4) for k, v in pred["probabilities"].items()},
        "expectedWoba": round(pred["expected_woba"], 3),
        "expectedPoints": round(pts, 1),
        "zDiffs": {k: round(v, 3) for k, v in pred["z_diffs"].items()},
    }
