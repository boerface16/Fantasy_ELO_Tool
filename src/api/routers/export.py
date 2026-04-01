"""Fantasy PDF export endpoint."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from src.fantasy.report import generate_pdf, save_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


class ExportRequest(BaseModel):
    roster_text: str
    ref_date: str | None = None


@router.post("/pdf")
async def export_pdf(req: ExportRequest):
    """Generate a PDF report for the given roster and week.

    Runs the weekly projection pipeline, then renders to PDF.
    Returns the PDF as a downloadable file.
    """
    from src.fantasy.roster_parser import parse_roster
    from src.fantasy.schedule_fetcher import fetch_week_schedule
    from src.fantasy.elo_lookup import EloLookup
    from src.fantasy.weekly_projection import project_week

    try:
        ref = date.fromisoformat(req.ref_date) if req.ref_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ref_date format. Use YYYY-MM-DD.")

    # Parse roster
    roster = parse_roster(req.roster_text)
    if not roster:
        raise HTTPException(status_code=400, detail="Could not parse any roster entries.")

    # Fetch schedule
    schedule = fetch_week_schedule(ref)

    # Load ELOs
    elo = EloLookup()
    player_ids = [e.player_id for e in roster if e.player_id]
    elo.load_batch(player_ids)

    # Project
    projection = project_week(roster, schedule, elo)

    # Serialize to dict (matching frontend JSON format)
    proj_dict = _serialize_projection(projection)

    # Fetch ELO enrichment data
    team_elos = _fetch_team_elos()
    player_elos = _fetch_player_elos(proj_dict)
    team_deltas = _fetch_team_elo_deltas()

    # Generate PDF and save a copy to disk
    pdf_bytes = generate_pdf(proj_dict, team_elos, player_elos=player_elos, team_deltas=team_deltas)
    save_pdf(proj_dict, team_elos, player_elos=player_elos, team_deltas=team_deltas)

    week_label = proj_dict.get("weekStart", "week")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="fantasy-report-{week_label}.pdf"'},
    )


def _serialize_projection(projection) -> dict:
    """Convert WeeklyProjection dataclass to JSON-friendly dict."""
    return {
        "weekStart": projection.week_start.isoformat(),
        "weekEnd": projection.week_end.isoformat(),
        "totalPoints": projection.total_points,
        "totalBatterPoints": projection.total_batter_points,
        "totalPitcherPoints": projection.total_pitcher_points,
        "batters": [
            {
                "name": b.player_name,
                "team": b.team,
                "slot": b.slot,
                "games": len(b.games),
                "totalPoints": b.total_points,
                "pointsPerGame": b.points_per_game,
                "matchups": [
                    {
                        "date": g.game_date.isoformat(),
                        "opponent": g.opponent_team,
                        "pitcher": g.opponent_pitcher_name,
                        "isHome": g.is_home,
                        "expectedWoba": g.expected_woba,
                        "expectedPoints": g.expected_points,
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
                "totalPoints": p.total_points,
                "matchups": [
                    {
                        "date": s.game_date.isoformat(),
                        "opponent": s.opponent_team,
                        "isHome": s.is_home,
                        "expectedWoba": s.expected_woba,
                        "expectedPoints": s.expected_points,
                    }
                    for s in p.starts
                ],
            }
            for p in projection.pitchers
        ],
    }


def _fetch_team_elos() -> list[dict]:
    """Fetch current team ELOs from Supabase."""
    try:
        from src.etl.upload_to_supabase import get_supabase_client
        client = get_supabase_client()
        resp = (
            client.table("team_elo")
            .select("team_code,elo_after,game_date")
            .order("game_date", desc=True)
            .limit(300)
            .execute()
        )
        seen = {}
        for row in (resp.data or []):
            tc = row["team_code"]
            if tc not in seen:
                seen[tc] = {"teamCode": tc, "elo": row["elo_after"]}
        return list(seen.values())
    except Exception:
        return []


def _fetch_team_elo_deltas() -> dict:
    """Fetch team ELO weekly deltas (current vs 7 days ago).

    Returns:
        dict {teamCode: {"elo": float, "weekDelta": float}}
    """
    try:
        from src.etl.upload_to_supabase import get_supabase_client
        client = get_supabase_client()
        cutoff = (date.today() - timedelta(days=7)).isoformat()

        # Get most recent ELO per team
        resp = (
            client.table("team_elo")
            .select("team_code,elo_after,game_date")
            .order("game_date", desc=True)
            .limit(300)
            .execute()
        )
        current = {}
        for row in (resp.data or []):
            tc = row["team_code"]
            if tc not in current:
                current[tc] = row["elo_after"]

        # Get ELO from ~7 days ago per team
        resp_old = (
            client.table("team_elo")
            .select("team_code,elo_after,game_date")
            .lte("game_date", cutoff)
            .order("game_date", desc=True)
            .limit(300)
            .execute()
        )
        old = {}
        for row in (resp_old.data or []):
            tc = row["team_code"]
            if tc not in old:
                old[tc] = row["elo_after"]

        result = {}
        for tc, elo in current.items():
            old_elo = old.get(tc, 1500.0)
            result[tc] = {"elo": elo, "weekDelta": elo - old_elo}
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch team ELO deltas: {e}")
        return {}


def _fetch_player_elos(proj_dict: dict) -> dict:
    """Fetch composite ELO + weekly delta for all players in the projection.

    Collects player IDs from batter/pitcher playerId fields and opponent pitcherId fields.

    Returns:
        dict {player_id: {"elo": float, "weekDelta": float}}
    """
    try:
        from src.etl.upload_to_supabase import get_supabase_client
        client = get_supabase_client()

        # Collect all player IDs we need
        pids = set()
        for b in proj_dict.get("batters", []):
            pid = b.get("playerId")
            if pid:
                pids.add(pid)
            for m in b.get("matchups", []):
                pitcher_id = m.get("pitcherId")
                if pitcher_id:
                    pids.add(pitcher_id)
        for p in proj_dict.get("pitchers", []):
            pid = p.get("playerId")
            if pid:
                pids.add(pid)

        if not pids:
            return {}

        pid_list = list(pids)

        # Fetch composite ELO from player_elo table
        result = {}
        for chunk_start in range(0, len(pid_list), 50):
            chunk = pid_list[chunk_start:chunk_start + 50]
            resp = (
                client.table("player_elo")
                .select("player_id,composite_elo")
                .in_("player_id", chunk)
                .execute()
            )
            for row in (resp.data or []):
                pid = row["player_id"]
                result[pid] = {"elo": row["composite_elo"], "weekDelta": 0.0}

        # Fetch weekly deltas from daily_ohlc (sum of delta over last 7 days)
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        for chunk_start in range(0, len(pid_list), 50):
            chunk = pid_list[chunk_start:chunk_start + 50]
            resp = (
                client.table("daily_ohlc")
                .select("player_id,delta")
                .in_("player_id", chunk)
                .gte("game_date", cutoff)
                .eq("elo_type", "SEASON")
                .execute()
            )
            # Sum deltas per player
            deltas: dict[int, float] = {}
            for row in (resp.data or []):
                pid = row["player_id"]
                deltas[pid] = deltas.get(pid, 0.0) + (row["delta"] or 0.0)
            for pid, delta in deltas.items():
                if pid in result:
                    result[pid]["weekDelta"] = delta

        return result
    except Exception as e:
        logger.warning(f"Failed to fetch player ELOs: {e}")
        return {}
