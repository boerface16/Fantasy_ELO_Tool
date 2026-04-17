"""Weekly projection orchestrator — combines all fantasy modules.

Flow: roster + schedule → opponent resolution → ELO lookup → matchup prediction → fantasy points.
"""

import logging
from dataclasses import dataclass, field as dc_field
from datetime import date

from src.fantasy.roster_parser import RosterEntry
from src.fantasy.schedule_fetcher import ScheduleGame
from src.fantasy.opponent_resolver import resolve_opponents, PITCHER_SLOTS, INACTIVE_SLOTS
from src.fantasy.elo_lookup import EloLookup, TEAM_ELO_MEAN, TEAM_ELO_STD, OPPONENT_WIN_WEIGHT
from src.fantasy.matchup_predictor import predict_plate_appearance, LEAGUE_AVG_WOBA
from src.fantasy.fantasy_calculator import (
    estimate_batter_points,
    estimate_pitcher_points,
    estimate_reliever_points,
    load_scoring_config,
    MLB_AVG_SB_PER_GAME,
)
from src.fantasy.fangraphs_enricher import get_pitcher_stats
from src.fantasy._config import get_config

logger = logging.getLogger(__name__)

_ENG = get_config()["prediction_engine"]

_CLUTCH_PITCHER_MEAN: float = _ENG["clutch_distribution"]["pitcher_mean"]
_CLUTCH_PITCHER_STD: float = _ENG["clutch_distribution"]["pitcher_std"]
_CLUTCH_WIN_WEIGHT: float = _ENG["clutch_win_weight"]

# Average PAs per game for a batter in the lineup
AVG_PA_PER_GAME = 3.9

# Composite ELO weights (aligned with fantasy scoring impact)
BATTER_ELO_WEIGHTS = {"contact": 0.30, "power": 0.35, "discipline": 0.25, "speed": 0.10}
PITCHER_ELO_WEIGHTS = {"stuff": 0.40, "command": 0.35, "bip_suppression": 0.25}


def compute_composite_elo(elo_dict: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted average of talent ELO dimensions."""
    return sum(elo_dict.get(k, 1500.0) * w for k, w in weights.items())

# Average batter ELO for pitcher projection (source of truth: config/multi_elo_config.yaml)
AVG_BATTER_ELO: dict[str, float] = _ENG["avg_batter_elo"]

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
    composite_elo: float = 1500.0
    eligible_positions: list[str] = dc_field(default_factory=list)


@dataclass
class PitcherProjection:
    player_id: int | None
    player_name: str
    team: str
    slot: str
    starts: list[GameMatchup]  # also used for RP appearances
    total_points: float = 0.0
    appearances: int = 0       # actual game count (starts for SP, appearances for RP)
    composite_elo: float = 1500.0


@dataclass
class WeeklyProjection:
    week_start: date
    week_end: date
    batters: list[BatterProjection] = dc_field(default_factory=list)
    pitchers: list[PitcherProjection] = dc_field(default_factory=list)
    total_batter_points: float = 0.0
    total_pitcher_points: float = 0.0
    total_points: float = 0.0
    optimal_batter_points: float = 0.0
    optimal_pitcher_points: float = 0.0
    optimal_total_points: float = 0.0


# ESPN lineup structure (actual league settings)
# Batters: C, 1B, 2B, SS, 3B, MI (2B/SS), CI (1B/3B), OF×5, UTIL (any)
LINEUP_SLOTS = {"C": 1, "1B": 1, "2B": 1, "SS": 1, "3B": 1, "MI": 1, "CI": 1, "OF": 5, "UTIL": 1}
PITCHER_LINEUP_COUNT = 9  # 9 pitchers per day, mix of SP and RP


def compute_optimal_lineup(
    batters: list[BatterProjection],
    pitchers: list[PitcherProjection],
) -> tuple[float, float]:
    """Compute optimal starting lineup points using actual ESPN lineup slots.

    Batters: C, 1B, 2B, SS, 3B, MI (2B or SS), CI (1B or 3B), OF×5, UTIL (any).
    Pitchers: top 9 by projected points (mix of SP/RP).

    Uses eligible_positions on each BatterProjection for flex-slot eligibility.
    Falls back to slot field if eligible_positions is empty (older parsed rosters).
    """
    sorted_batters = sorted(batters, key=lambda b: b.total_points, reverse=True)
    used: set[int] = set()
    selected_batter_pts = 0.0

    def _eligible(b: BatterProjection) -> list[str]:
        """Return the positions to use for eligibility checks."""
        return b.eligible_positions if b.eligible_positions else [b.slot]

    def _fill(n: int, qualifies) -> None:
        nonlocal selected_batter_pts
        count = 0
        for b in sorted_batters:
            if count >= n:
                break
            if id(b) not in used and qualifies(_eligible(b)):
                used.add(id(b))
                selected_batter_pts += b.total_points
                count += 1

    # Fill positional slots first (most restrictive → least restrictive)
    _fill(1, lambda pos: "C" in pos)
    _fill(1, lambda pos: "1B" in pos)
    _fill(1, lambda pos: "2B" in pos)
    _fill(1, lambda pos: "SS" in pos)
    _fill(1, lambda pos: "3B" in pos)
    _fill(1, lambda pos: "2B" in pos or "SS" in pos)   # MI
    _fill(1, lambda pos: "1B" in pos or "3B" in pos)   # CI
    _fill(5, lambda pos: "OF" in pos)                   # OF × 5
    _fill(1, lambda pos: True)                          # UTIL — any remaining batter

    # Pitchers: top 9 by total weekly projected points
    sorted_pitchers = sorted(pitchers, key=lambda p: p.total_points, reverse=True)
    selected_pitcher_pts = sum(p.total_points for p in sorted_pitchers[:PITCHER_LINEUP_COUNT])

    return selected_batter_pts, selected_pitcher_pts


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

    # ME-4: pre-load team ELO for all opponent teams encountered this week
    if supabase:
        all_opponent_teams = list({m.opponent_team for m in matchups if m.opponent_team})
        elo_lookup.load_teams(all_opponent_teams)

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

        # Composite ELO for display
        full_batter_elo = elo_lookup.get_batter_elo(batter_player_id or 0)
        batter_composite = compute_composite_elo(full_batter_elo, BATTER_ELO_WEIGHTS)

        for m in player_matchups:
            # Opponent pitcher ELO
            if m.opponent_pitcher_id:
                pitcher_elo = elo_lookup.get_pitcher_elo(m.opponent_pitcher_id)
            else:
                pitcher_elo = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0, "clutch": 1500.0}

            # Actual batter ELO (uses player_id from roster; defaults to 1500 if not found)
            batter_elo = elo_lookup.get_batter_elo(m.player_id or 0)
            if not m.player_id:
                logger.warning(f"No player_id for {m.player_name} ({m.player_team}) — using default ELO")
            elif all(v == 1500.0 for k, v in batter_elo.items() if k not in ("speed", "clutch")):
                logger.warning(f"No talent ELO in DB for {m.player_name} (id={m.player_id}) — using defaults")
            speed_elo = batter_elo.pop("speed", 1500.0)    # separate — SB projection only
            clutch_elo = batter_elo.pop("clutch", 1500.0)  # ME-2: used for high-leverage blend

            # ME-1: apply recent-form adjustment (OHLC 7-day momentum) to each batter dimension
            if supabase and m.player_id:
                for dim in list(batter_elo):
                    batter_elo[dim] *= elo_lookup.get_recent_form_adjustment(m.player_id, dim)

            pred = predict_plate_appearance(
                batter_elo, pitcher_elo,
                clutch_elo=clutch_elo,
                is_home=m.is_home,
                speed_elo=speed_elo,    # LR-2: drives dynamic 3B ratio
            )

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

        eligible = player_matchups[0].eligible_positions if player_matchups else []
        batters.append(BatterProjection(
            player_id=batter_player_id, player_name=name, team=team, slot=slot,
            games=games, total_points=total_pts, points_per_game=ppg,
            composite_elo=batter_composite,
            eligible_positions=eligible,
        ))

    # -------------------------------------------------------------------------
    # Project pitchers (SP starts + RP appearances)
    # -------------------------------------------------------------------------
    pitchers = []
    for key, player_matchups in pitcher_matchups.items():
        name, team, slot = key.split("|")

        sp_starts = [m for m in player_matchups if m.is_start]
        rp_slots = [m for m in player_matchups if not m.is_start]

        # Composite ELO for display
        pitcher_pid = (sp_starts[0].player_id if sp_starts else None) or \
                      (rp_slots[0].player_id if rp_slots else None)
        pitcher_composite = compute_composite_elo(
            elo_lookup.get_pitcher_elo(pitcher_pid or 0), PITCHER_ELO_WEIGHTS
        )

        starts = []

        # --- SP: project each scheduled start ---
        for m in sp_starts:
            pitcher_own_elo = elo_lookup.get_pitcher_elo(m.player_id or 0)

            # ME-1: apply recent-form adjustment to each pitcher dimension
            if supabase and m.player_id:
                for dim in list(pitcher_own_elo):
                    pitcher_own_elo[dim] *= elo_lookup.get_recent_form_adjustment(m.player_id, dim)

            pitcher_pred = predict_plate_appearance(AVG_BATTER_ELO, pitcher_own_elo)

            # Win/loss probability from pitcher quality vs league average
            woba_diff = LEAGUE_AVG_WOBA - pitcher_pred["expected_woba"]
            # QW-1: clutch ELO shift — high-leverage performance predicts win rate
            clutch_elo = pitcher_own_elo.get("clutch", 1500.0)
            z_clutch = (clutch_elo - _CLUTCH_PITCHER_MEAN) / _CLUTCH_PITCHER_STD if _CLUTCH_PITCHER_STD > 0 else 0.0
            win_prob = max(0.10, min(0.55, BASE_WIN_PROB + woba_diff * 0.5 + z_clutch * _CLUTCH_WIN_WEIGHT))
            loss_prob = max(0.05, min(0.40, BASE_LOSS_PROB - woba_diff * 0.3))

            # ME-4: opponent team strength — stronger teams reduce win probability
            opp_team_elo = elo_lookup.get_team_elo(m.opponent_team)
            opp_z = (opp_team_elo - TEAM_ELO_MEAN) / TEAM_ELO_STD if TEAM_ELO_STD > 0 else 0.0
            win_prob = max(0.10, min(0.55, win_prob - opp_z * OPPONENT_WIN_WEIGHT))

            # QW-4: use actual IP/GS from Fangraphs instead of fixed 6.0
            fg_sp = fg_by_name.get(name.lower(), {})
            gs = float(fg_sp.get("GS") or 0)
            season_ip_sp = float(fg_sp.get("IP") or 0)
            avg_ip = max(4.0, min(7.5, season_ip_sp / gs)) if gs > 0 else 6.0

            pts = estimate_pitcher_points(
                pitcher_pred["probabilities"], scoring,
                innings=avg_ip, win_prob=win_prob, loss_prob=loss_prob,
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
        weekly_appearances = 0
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
        app_count = len(sp_starts) + (round(weekly_appearances) if rp_slots else 0)

        pitcher_player_id = (sp_starts[0].player_id if sp_starts else None) or \
                            (rp_slots[0].player_id if rp_slots else None)
        pitchers.append(PitcherProjection(
            player_id=pitcher_player_id, player_name=name, team=team, slot=slot,
            starts=starts, total_points=total_pts,
            appearances=app_count, composite_elo=pitcher_composite,
        ))

    total_batter = sum(b.total_points for b in batters)
    total_pitcher = sum(p.total_points for p in pitchers)

    sorted_batters = sorted(batters, key=lambda b: b.total_points, reverse=True)
    sorted_pitchers = sorted(pitchers, key=lambda p: p.total_points, reverse=True)

    opt_bat, opt_pit = compute_optimal_lineup(sorted_batters, sorted_pitchers)

    return WeeklyProjection(
        week_start=week_start,
        week_end=week_end,
        batters=sorted_batters,
        pitchers=sorted_pitchers,
        total_batter_points=total_batter,
        total_pitcher_points=total_pitcher,
        total_points=total_batter + total_pitcher,
        optimal_batter_points=opt_bat,
        optimal_pitcher_points=opt_pit,
        optimal_total_points=opt_bat + opt_pit,
    )
