"""Weekly projection orchestrator — combines all fantasy modules.

Flow: roster + schedule → opponent resolution → ELO lookup → matchup prediction → fantasy points.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame
from src.fantasy.opponent_resolver import resolve_opponents, PITCHER_SLOTS, INACTIVE_SLOTS
from src.fantasy.elo_lookup import EloLookup
from src.fantasy.matchup_predictor import predict_plate_appearance, LEAGUE_AVG_WOBA
from src.fantasy.fantasy_calculator import (
    estimate_batter_points,
    estimate_pitcher_points,
    estimate_reliever_points,
    load_scoring_config,
    MLB_AVG_SB_PER_GAME,
)
from src.fantasy.fangraphs_enricher import get_pitcher_stats

logger = logging.getLogger(__name__)

# Average PAs per game for a batter in the lineup
AVG_PA_PER_GAME = 3.9

# Average batter ELO for pitcher projection
AVG_BATTER_ELO = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}

# SP win/loss base rates (MLB averages)
BASE_WIN_PROB = 0.28
BASE_LOSS_PROB = 0.18

# Minimum historical PAs vs team needed to apply any blend weight
MIN_HISTORY_PA = 10

# Result type → probability key mapping for history blend
_RT_TO_PROB = {
    "Single": "1B", "Double": "2B", "Triple": "3B", "HR": "HR",
    "BB": "BB", "IBB": "BB", "HBP": "BB",
    "StrikeOut": "K",
    "OUT": "OUT", "FC": "OUT", "GIDP": "OUT",
    "POPUP": "OUT", "GROUNDOUT": "OUT", "SAC": "OUT", "E": "OUT",
}


@dataclass
class GameMatchup:
    game_date: date
    opponent_team: str
    opponent_pitcher_name: str
    is_home: bool
    expected_woba: float
    expected_points: float
    probabilities: dict[str, float]


@dataclass
class BatterProjection:
    player_id: int | None
    player_name: str
    team: str
    slot: str
    games: list[GameMatchup]
    total_points: float = 0.0
    points_per_game: float = 0.0


@dataclass
class PitcherProjection:
    player_id: int | None
    player_name: str
    team: str
    slot: str
    starts: list[GameMatchup]  # also used for RP appearances
    total_points: float = 0.0
    appearances: int = 0       # actual game count (starts for SP, appearances for RP)


@dataclass
class WeeklyProjection:
    week_start: date
    week_end: date
    batters: list[BatterProjection] = field(default_factory=list)
    pitchers: list[PitcherProjection] = field(default_factory=list)
    total_batter_points: float = 0.0
    total_pitcher_points: float = 0.0
    total_points: float = 0.0


def _get_historical_probs(supabase, batter_id: int, opponent_team: str) -> tuple[dict, int]:
    """Query batter's historical PA outcomes vs pitchers currently on opponent team.

    Returns (prob_dict, sample_size).
    """
    if not batter_id or not opponent_team:
        return {}, 0

    # Get pitcher IDs currently on the opponent team
    resp = (
        supabase.table("players")
        .select("player_id")
        .eq("team", opponent_team)
        .execute()
    )
    opponent_pitcher_ids = [r["player_id"] for r in (resp.data or [])]
    if not opponent_pitcher_ids:
        return {}, 0

    # Query historical PAs (Supabase IN has a practical limit; batch if needed)
    ids_batch = opponent_pitcher_ids[:100]
    resp = (
        supabase.table("plate_appearances")
        .select("result_type")
        .eq("batter_id", batter_id)
        .in_("pitcher_id", ids_batch)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {}, 0

    counts: dict[str, int] = {}
    for row in rows:
        rt = row["result_type"]
        counts[rt] = counts.get(rt, 0) + 1

    n = len(rows)
    probs: dict[str, float] = {"BB": 0.0, "K": 0.0, "OUT": 0.0, "1B": 0.0, "2B": 0.0, "3B": 0.0, "HR": 0.0}
    for rt, cnt in counts.items():
        key = _RT_TO_PROB.get(rt)
        if key:
            probs[key] = probs.get(key, 0.0) + cnt / n
    return probs, n


def _blend_probs(elo_probs: dict, hist_probs: dict, n: int) -> dict:
    """Blend ELO-based probs with historical probs, weight capped at 30%."""
    if n < MIN_HISTORY_PA or not hist_probs:
        return elo_probs
    alpha = min(0.30, n / 333)
    return {k: (1 - alpha) * elo_probs.get(k, 0.0) + alpha * hist_probs.get(k, 0.0)
            for k in elo_probs}


def project_week(
    roster: list[RosterEntry],
    schedule: list[ScheduleGame],
    elo_lookup: EloLookup,
    supabase=None,
) -> WeeklyProjection:
    """Generate weekly fantasy projection.

    Args:
        roster: parsed roster entries (player_id should be populated for best results)
        schedule: weekly schedule with probable pitchers
        elo_lookup: pre-loaded ELO lookup cache
        supabase: Supabase client for history lookups (optional)

    Returns:
        WeeklyProjection with per-player breakdowns
    """
    scoring = load_scoring_config()
    matchups = resolve_opponents(roster, schedule)

    # Determine week range from schedule
    if schedule:
        week_start = min(g.game_date for g in schedule)
        week_end = max(g.game_date for g in schedule)
    else:
        week_start = week_end = date.today()

    # Fetch Fangraphs pitching stats once (cached daily) for RP projection
    try:
        pitcher_fg = get_pitcher_stats(week_start.year)
        fg_by_name = {str(row["Name"]).lower(): row for _, row in pitcher_fg.iterrows()}
    except Exception as e:
        logger.warning(f"Could not load Fangraphs pitcher stats: {e}")
        fg_by_name = {}

    # Group matchups by player
    batter_matchups: dict[str, list] = {}
    pitcher_matchups: dict[str, list] = {}

    for m in matchups:
        entry_key = f"{m.player_name}|{m.player_team}|{m.slot}"
        if m.slot in PITCHER_SLOTS:
            pitcher_matchups.setdefault(entry_key, []).append(m)
        else:
            batter_matchups.setdefault(entry_key, []).append(m)

    # -------------------------------------------------------------------------
    # Project batters
    # -------------------------------------------------------------------------
    batters = []
    for key, player_matchups in batter_matchups.items():
        name, team, slot = key.split("|")
        games = []
        batter_player_id = player_matchups[0].player_id if player_matchups else None

        for m in player_matchups:
            # Opponent pitcher ELO
            if m.opponent_pitcher_id:
                pitcher_elo = elo_lookup.get_pitcher_elo(m.opponent_pitcher_id)
            else:
                pitcher_elo = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0}

            # Actual batter ELO (uses player_id from roster; defaults to 1500 if not found)
            batter_elo = elo_lookup.get_batter_elo(m.player_id or 0)
            if not m.player_id:
                logger.warning(f"No player_id for {m.player_name} ({m.player_team}) — using default ELO")
            elif all(v == 1500.0 for k, v in batter_elo.items() if k != "speed"):
                logger.warning(f"No talent ELO in DB for {m.player_name} (id={m.player_id}) — using defaults")
            speed_elo = batter_elo.pop("speed", 1500.0)  # separate — not used in matchup predictor

            pred = predict_plate_appearance(batter_elo, pitcher_elo)

            # History blend: how has this batter done vs this opponent team?
            final_probs = pred["probabilities"]
            if supabase and m.player_id:
                hist_probs, hist_n = _get_historical_probs(supabase, m.player_id, m.opponent_team)
                final_probs = _blend_probs(pred["probabilities"], hist_probs, hist_n)

            # Pitcher SB-allow factor from Fangraphs
            pitcher_sb_factor = 1.0
            opp_name = (m.opponent_pitcher_name or "").lower()
            fg_p = fg_by_name.get(opp_name, {})
            season_g_p = float(fg_p.get("G") or 0)
            season_sb_p = float(fg_p.get("SB") or 0)
            if season_g_p > 0:
                pitcher_rate = season_sb_p / season_g_p
                pitcher_sb_factor = pitcher_rate / MLB_AVG_SB_PER_GAME if MLB_AVG_SB_PER_GAME > 0 else 1.0
                pitcher_sb_factor = max(0.1, min(3.0, pitcher_sb_factor))  # clamp

            pts = estimate_batter_points(
                final_probs, scoring,
                pas=AVG_PA_PER_GAME,
                speed_elo=speed_elo,
                pitcher_sb_factor=pitcher_sb_factor,
            )

            games.append(GameMatchup(
                game_date=m.game_date,
                opponent_team=m.opponent_team,
                opponent_pitcher_name=m.opponent_pitcher_name,
                is_home=m.is_home,
                expected_woba=pred["expected_woba"],
                expected_points=pts,
                probabilities=final_probs,
            ))

        total_pts = sum(g.expected_points for g in games)
        ppg = total_pts / len(games) if games else 0.0

        batters.append(BatterProjection(
            player_id=batter_player_id, player_name=name, team=team, slot=slot,
            games=games, total_points=total_pts, points_per_game=ppg,
        ))

    # -------------------------------------------------------------------------
    # Project pitchers (SP starts + RP appearances)
    # -------------------------------------------------------------------------
    pitchers = []
    for key, player_matchups in pitcher_matchups.items():
        name, team, slot = key.split("|")

        sp_starts = [m for m in player_matchups if m.is_start]
        rp_slots = [m for m in player_matchups if not m.is_start]

        starts = []

        # --- SP: project each scheduled start ---
        for m in sp_starts:
            pitcher_own_elo = elo_lookup.get_pitcher_elo(m.player_id or 0)
            pitcher_pred = predict_plate_appearance(AVG_BATTER_ELO, pitcher_own_elo)

            # Win/loss probability from pitcher quality vs league average
            woba_diff = LEAGUE_AVG_WOBA - pitcher_pred["expected_woba"]
            win_prob = max(0.10, min(0.55, BASE_WIN_PROB + woba_diff * 0.5))
            loss_prob = max(0.05, min(0.40, BASE_LOSS_PROB - woba_diff * 0.3))

            pts = estimate_pitcher_points(
                pitcher_pred["probabilities"], scoring,
                innings=6.0, win_prob=win_prob, loss_prob=loss_prob,
            )

            starts.append(GameMatchup(
                game_date=m.game_date,
                opponent_team=m.opponent_team,
                opponent_pitcher_name=f"vs {m.opponent_team}",
                is_home=m.is_home,
                expected_woba=pitcher_pred["expected_woba"],
                expected_points=pts,
                probabilities=pitcher_pred["probabilities"],
            ))

        # --- RP: project from Fangraphs rates across all team games ---
        if rp_slots:
            fg = fg_by_name.get(name.lower(), {})
            season_g = float(fg.get("G") or 0) or 30.0
            season_ip = float(fg.get("IP") or 0) or season_g
            season_sv = float(fg.get("SV") or 0)
            season_hld = float(fg.get("HLD") or 0)

            SEASON_GAMES = 162.0
            appearance_rate = min(season_g / SEASON_GAMES, 0.85)
            ip_per_app = max(0.5, min(2.0, season_ip / season_g)) if season_g > 0 else 1.0
            sv_per_app = season_sv / season_g if season_g > 0 else 0.0
            hld_per_app = season_hld / season_g if season_g > 0 else 0.0

            team_games = len(rp_slots)
            weekly_appearances = team_games * appearance_rate

            pitcher_own_elo = elo_lookup.get_pitcher_elo(rp_slots[0].player_id or 0)
            pitcher_pred = predict_plate_appearance(AVG_BATTER_ELO, pitcher_own_elo)

            pts = estimate_reliever_points(
                pitcher_pred["probabilities"], scoring,
                appearances=weekly_appearances,
                sv_per_app=sv_per_app,
                hld_per_app=hld_per_app,
                ip_per_app=ip_per_app,
            )

            # One synthetic entry representing the full week of relief work
            rep_slot = rp_slots[0]
            starts.append(GameMatchup(
                game_date=rep_slot.game_date,
                opponent_team=rep_slot.opponent_team,
                opponent_pitcher_name=f"RP ({team_games}G, {weekly_appearances:.1f} app)",
                is_home=rep_slot.is_home,
                expected_woba=pitcher_pred["expected_woba"],
                expected_points=pts,
                probabilities=pitcher_pred["probabilities"],
            ))

        if not starts:
            continue  # SP not scheduled this week and no RP slots

        total_pts = sum(s.expected_points for s in starts)
        app_count = len(sp_starts) + (len(rp_slots) if rp_slots else 0)

        pitcher_player_id = (sp_starts[0].player_id if sp_starts else None) or \
                            (rp_slots[0].player_id if rp_slots else None)
        pitchers.append(PitcherProjection(
            player_id=pitcher_player_id, player_name=name, team=team, slot=slot,
            starts=starts, total_points=total_pts,
            appearances=app_count,
        ))

    total_batter = sum(b.total_points for b in batters)
    total_pitcher = sum(p.total_points for p in pitchers)

    return WeeklyProjection(
        week_start=week_start,
        week_end=week_end,
        batters=sorted(batters, key=lambda b: b.total_points, reverse=True),
        pitchers=sorted(pitchers, key=lambda p: p.total_points, reverse=True),
        total_batter_points=total_batter,
        total_pitcher_points=total_pitcher,
        total_points=total_batter + total_pitcher,
    )
