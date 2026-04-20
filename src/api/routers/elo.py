"""ELO endpoints — ports of frontend/src/api/elo.ts Supabase queries."""

import asyncio
import yaml
import os
from datetime import date as _date
import httpx
from fastapi import APIRouter, Query
from src.api.deps import get_supabase

_MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


def _parse_ip(ip_str: str) -> float:
    """Convert baseball IP notation string to true decimal innings.
    '7.0' → 7.0, '7.1' → 7.333, '7.2' → 7.667
    """
    parts = str(ip_str).split(".")
    full = int(parts[0])
    outs = int(parts[1]) if len(parts) > 1 else 0
    return full + outs / 3.0


def _fetch_pitcher_game_log(player_id: int, season: int) -> dict[int, dict]:
    """Fetch actual per-game pitching stats from MLB Stats API, keyed by gamePk.
    Returns empty dict on failure (caller falls back to PA-derived stats).
    """
    url = (
        f"{_MLB_STATS_BASE}/people/{player_id}/stats"
        f"?stats=gameLog&group=pitching&season={season}&gameType=R"
    )
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        splits = resp.json().get("stats", [{}])[0].get("splits", [])
    except Exception:
        return {}

    result = {}
    for split in splits:
        gpk = split.get("game", {}).get("gamePk")
        st = split.get("stat", {})
        if not gpk:
            continue
        result[gpk] = {
            "ip":  _parse_ip(str(st.get("inningsPitched", "0.0"))),
            "h":   int(st.get("hits", 0)),
            "er":  int(st.get("earnedRuns", 0)),
            "hr":  int(st.get("homeRuns", 0)),
            "bb":  int(st.get("baseOnBalls", 0)),
            "k":   int(st.get("strikeOuts", 0)),
            "hb":  int(st.get("hitByPitch", 0)),
            "w":   int(st.get("wins", 0)),
            "l":   int(st.get("losses", 0)),
            "sv":  int(st.get("saves", 0)),
            "bs":  int(st.get("blownSaves", 0)),
            "cg":  int(st.get("completeGames", 0)),
            "sho": int(st.get("shutouts", 0)),
            "b":   int(st.get("balks", 0)),
            "pko": int(st.get("pickoffs", 0)),
        }
    return result


def _fetch_batter_game_log(player_id: int, season: int) -> dict[int, dict]:
    """Fetch actual per-game hitting stats from MLB Stats API, keyed by gamePk.
    Returns empty dict on failure (caller falls back to PA-derived stats).
    """
    url = (
        f"{_MLB_STATS_BASE}/people/{player_id}/stats"
        f"?stats=gameLog&group=hitting&season={season}&gameType=R"
    )
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        splits = resp.json().get("stats", [{}])[0].get("splits", [])
    except Exception:
        return {}

    result = {}
    for split in splits:
        gpk = split.get("game", {}).get("gamePk")
        st = split.get("stat", {})
        if not gpk:
            continue
        result[gpk] = {
            "pa":  int(st.get("plateAppearances", 0)),
            "tb":  int(st.get("totalBases", 0)),
            "r":   int(st.get("runs", 0)),
            "rbi": int(st.get("rbi", 0)),
            "hr":  int(st.get("homeRuns", 0)),
            "bb":  int(st.get("baseOnBalls", 0)) + int(st.get("intentionalWalks", 0)),
            "k":   int(st.get("strikeOuts", 0)),
            "sb":  int(st.get("stolenBases", 0)),
        }
    return result


def _pitcher_pts_actual(stats: dict, rules: dict) -> float:
    """Compute fantasy points from actual MLB boxscore pitching stats (no estimation)."""
    return (
        stats["ip"]  * rules.get("IP",   3)
        + stats["k"]   * rules.get("K",    1)
        + stats["h"]   * rules.get("H",   -1)
        + stats["er"]  * rules.get("ER",  -1)
        + stats["hr"]  * rules.get("HR",  -1)
        + stats["bb"]  * rules.get("BB",  -1)
        + stats["hb"]  * rules.get("HB",   1)
        + stats["w"]   * rules.get("W",    5)
        + stats["l"]   * rules.get("L",   -5)
        + stats["sv"]  * rules.get("SV",   5)
        + stats["bs"]  * rules.get("BS",  -5)
        + stats["cg"]  * rules.get("CG",   3)
        + stats["sho"] * rules.get("SHO",  5)
        + stats["b"]   * rules.get("B",  -10)
        + stats["pko"] * rules.get("PKO",  2)
    )


def _batter_pts_actual(stats: dict, rules: dict) -> float:
    """Compute fantasy points from actual MLB boxscore hitting stats."""
    return (
        stats["tb"]  * rules.get("TB",  1)
        + stats["r"]   * rules.get("R",   1)
        + stats["rbi"] * rules.get("RBI", 1)
        + stats["bb"]  * rules.get("BB",  1)
        + stats["sb"]  * rules.get("SB",  1)
        + stats["k"]   * rules.get("SO", -1)
        # E: not in hitting game log; always 0
    )


async def _fetch_batter_day_stats_batch(
    player_ids: list[int], game_date: str, season: int
) -> dict[int, dict | None]:
    """Fetch actual hitting stats for multiple players on a given date, in parallel."""

    async def fetch_one(client: httpx.AsyncClient, player_id: int) -> tuple[int, dict | None]:
        url = (
            f"{_MLB_STATS_BASE}/people/{player_id}/stats"
            f"?stats=gameLog&group=hitting&season={season}&gameType=R"
        )
        try:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            splits = resp.json().get("stats", [{}])[0].get("splits", [])
            for split in splits:
                if split.get("date") == game_date:
                    st = split.get("stat", {})
                    return player_id, {
                        "pa":  int(st.get("plateAppearances", 0)),
                        "tb":  int(st.get("totalBases", 0)),
                        "r":   int(st.get("runs", 0)),
                        "rbi": int(st.get("rbi", 0)),
                        "hr":  int(st.get("homeRuns", 0)),
                        "bb":  int(st.get("baseOnBalls", 0)) + int(st.get("intentionalWalks", 0)),
                        "k":   int(st.get("strikeOuts", 0)),
                        "sb":  int(st.get("stolenBases", 0)),
                    }
        except Exception:
            pass
        return player_id, None

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[fetch_one(client, pid) for pid in player_ids])

    return dict(results)

_SCORING_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "espn_scoring.yaml")

def _load_scoring():
    with open(_SCORING_PATH) as f:
        return yaml.safe_load(f)

def _batter_pts(rt_counts: dict, rules: dict) -> float:
    s = rt_counts.get("Single", 0)
    d = rt_counts.get("Double", 0)
    t = rt_counts.get("Triple", 0)
    hr = rt_counts.get("HR", 0)
    bb = rt_counts.get("BB", 0) + rt_counts.get("IBB", 0)
    k = rt_counts.get("StrikeOut", 0)
    sb = rt_counts.get("SB", 0)
    e = rt_counts.get("E", 0)
    tb = s + d * 2 + t * 3 + hr * 4
    return (
        tb * rules.get("TB", 1)
        + tb * 0.40 * rules.get("R", 1)
        + tb * 0.45 * rules.get("RBI", 1)
        + bb * rules.get("BB", 1)
        + sb * rules.get("SB", 1)
        + k * rules.get("SO", -1)
        + e * rules.get("E", -3)
    )

def _pitcher_pts(rt_counts: dict, rules: dict) -> float:
    k = rt_counts.get("StrikeOut", 0)
    bb = rt_counts.get("BB", 0) + rt_counts.get("IBB", 0)
    hb = rt_counts.get("HBP", 0)
    hr = rt_counts.get("HR", 0)
    h = (rt_counts.get("Single", 0) + rt_counts.get("Double", 0)
         + rt_counts.get("Triple", 0) + hr)
    outs = rt_counts.get("OUT", 0) + rt_counts.get("POPUP", 0) + rt_counts.get("GROUNDOUT", 0) + k
    ip = outs / 3.0
    er_est = (h + bb + hb) * 0.30
    return (
        ip * rules.get("IP", 3)
        + k * rules.get("K", 1)
        + h * rules.get("H", -1)
        + hr * rules.get("HR", -1)
        + er_est * rules.get("ER", -1)
        + bb * rules.get("BB", -1)
        + hb * rules.get("HB", 1)
    )

router = APIRouter()


@router.get("/hot-players")
async def hot_players(date: str, role: str = Query("BATTING")):
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("player_id, game_date, open, high, low, close, delta, total_pa, players!inner(full_name, team, position)")
        .eq("game_date", date)
        .eq("elo_type", "SEASON")
        .eq("role", role)
        .order("delta", desc=True)
        .limit(10)
        .execute()
    )
    return [_flatten_ohlc_player(row) for row in resp.data]


@router.get("/cold-players")
async def cold_players(date: str, role: str = Query("BATTING")):
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("player_id, game_date, open, high, low, close, delta, total_pa, players!inner(full_name, team, position)")
        .eq("game_date", date)
        .eq("elo_type", "SEASON")
        .eq("role", role)
        .order("delta", desc=False)
        .limit(10)
        .execute()
    )
    return [_flatten_ohlc_player(row) for row in resp.data]


@router.get("/leaderboard")
async def leaderboard(
    position: str = Query("batter"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    team: str = Query(None),
    days: int = Query(None, ge=1, le=365),
    from_date: str = Query(None),
):
    sb = get_supabase()
    offset = (page - 1) * limit

    if days is not None or from_date is not None:
        from datetime import datetime, timedelta
        from collections import defaultdict
        if days is not None:
            start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        else:
            start_date = from_date
        ohlc_role = "PITCHING" if position == "pitcher" else "BATTING"

        query = (
            sb.table("daily_ohlc")
            .select("player_id, delta, total_pa, players!inner(full_name, team, position)")
            .gte("game_date", start_date)
            .eq("elo_type", "SEASON")
            .eq("role", ohlc_role)
            .limit(10000)
        )
        if team:
            query = query.eq("players.team", team)
        resp = query.execute()

        agg: dict = defaultdict(lambda: {"elo_delta": 0.0, "pa_count": 0})
        player_info: dict = {}
        for row in resp.data or []:
            pid = row["player_id"]
            agg[pid]["elo_delta"] += row["delta"] or 0.0
            agg[pid]["pa_count"] += row["total_pa"] or 0
            player_info[pid] = row["players"]

        # Exclude position players who made a garbage-time appearance in the wrong role
        min_pa = 5 if position == "pitcher" else 3
        filtered = [(pid, data) for pid, data in agg.items() if data["pa_count"] >= min_pa]
        sorted_results = sorted(filtered, key=lambda x: x[1]["elo_delta"], reverse=True)
        page_slice = sorted_results[offset: offset + limit]
        return [
            {
                "player_id": pid,
                "elo_delta": round(data["elo_delta"], 1),
                "batting_elo": None,
                "pitching_elo": None,
                "composite_elo": None,
                "pa_count": data["pa_count"],
                "batting_pa": data["pa_count"] if position == "batter" else 0,
                "pitching_pa": data["pa_count"] if position == "pitcher" else 0,
                "last_game_date": None,
                "full_name": player_info[pid]["full_name"],
                "team": player_info[pid]["team"],
                "position": player_info[pid]["position"],
            }
            for pid, data in page_slice
        ]

    sort_column = "pitching_elo" if position == "pitcher" else "batting_elo"
    pa_column = "pitching_pa" if position == "pitcher" else "batting_pa"

    query = (
        sb.table("player_elo")
        .select("player_id, composite_elo, batting_elo, pitching_elo, pa_count, batting_pa, pitching_pa, last_game_date, players!inner(full_name, team, position)")
        .gt(pa_column, 0)
        .order(sort_column, desc=True)
        .range(offset, offset + limit - 1)
    )
    if team:
        query = query.eq("players.team", team)
    resp = query.execute()
    return [_flatten_leaderboard(row) for row in resp.data]


@router.get("/players/{player_id}")
async def player_elo(player_id: int):
    sb = get_supabase()
    resp = (
        sb.table("player_elo")
        .select("player_id, composite_elo, batting_elo, pitching_elo, pa_count, batting_pa, pitching_pa, last_game_date, players!inner(player_id, full_name, team, position)")
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    row = resp.data
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "composite_elo": row["composite_elo"],
        "batting_elo": row.get("batting_elo") or 1500,
        "pitching_elo": row.get("pitching_elo") or 1500,
        "pa_count": row["pa_count"],
        "batting_pa": row.get("batting_pa") or 0,
        "pitching_pa": row.get("pitching_pa") or 0,
        "last_game_date": row["last_game_date"],
        "player": {
            "player_id": p["player_id"],
            "full_name": p["full_name"],
            "team": p["team"],
            "position": p["position"],
        },
    }


@router.get("/players/{player_id}/ohlc")
async def player_ohlc(player_id: int, role: str = Query("BATTING"), season: int = None):
    sb = get_supabase()
    query = (
        sb.table("daily_ohlc")
        .select("game_date, open, high, low, close, delta, total_pa, role")
        .eq("player_id", player_id)
        .eq("elo_type", "SEASON")
        .eq("role", role)
        .order("game_date")
    )
    if season:
        query = query.gte("game_date", f"{season}-01-01").lt("game_date", f"{season + 1}-01-01")

    resp = query.execute()
    return resp.data


@router.get("/players/{player_id}/stats")
async def player_stats(player_id: int, role: str = "BATTING"):
    ohlc_data = (await player_ohlc(player_id, role))

    if not ohlc_data:
        return {
            "totalPa": 0,
            "avgDelta": 0,
            "highestElo": {"value": 1500, "date": ""},
            "lowestElo": {"value": 1500, "date": ""},
            "avgRange": 0,
        }

    total_pa = sum(d["total_pa"] for d in ohlc_data)
    avg_delta = sum(d["delta"] for d in ohlc_data) / len(ohlc_data)

    highest = {"value": float("-inf"), "date": ""}
    lowest = {"value": float("inf"), "date": ""}
    range_sum = 0.0

    for d in ohlc_data:
        if d["high"] > highest["value"]:
            highest = {"value": d["high"], "date": d["game_date"]}
        if d["low"] < lowest["value"]:
            lowest = {"value": d["low"], "date": d["game_date"]}
        range_sum += d["high"] - d["low"]

    return {
        "totalPa": total_pa,
        "avgDelta": avg_delta,
        "highestElo": highest,
        "lowestElo": lowest,
        "avgRange": range_sum / len(ohlc_data),
    }


@router.get("/players/{player_id}/games")
async def player_games(
    player_id: int,
    role: str = Query("BATTING"),
    limit: int = Query(5, ge=1, le=20),
):
    """Last N games for a player: date, opponent, ELO, ELO delta, fantasy points."""
    sb = get_supabase()

    id_col = "pitcher_id" if role == "PITCHING" else "batter_id"
    resp = (
        sb.table("plate_appearances")
        .select("game_pk, game_date, result_type, inning_half, home_team, away_team")
        .eq(id_col, player_id)
        .order("game_date", desc=True)
        .limit(400)
        .execute()
    )

    # Group by game_pk preserving recency order
    games: dict[int, dict] = {}
    game_order: list[int] = []
    for row in resp.data or []:
        gpk = row["game_pk"]
        if gpk not in games:
            games[gpk] = {
                "game_pk": gpk,
                "game_date": row["game_date"],
                "home_team": row["home_team"] or "",
                "away_team": row["away_team"] or "",
                "inning_half": row["inning_half"] or "Top",
                "result_types": [],
            }
            game_order.append(gpk)
        games[gpk]["result_types"].append(row["result_type"])

    recent_pks = game_order[:limit]
    if not recent_pks:
        return {"games": []}

    # Fetch daily_ohlc for relevant dates
    dates = list({games[pk]["game_date"] for pk in recent_pks})
    ohlc_resp = (
        sb.table("daily_ohlc")
        .select("game_date, close, delta, role")
        .eq("player_id", player_id)
        .eq("elo_type", "SEASON")
        .eq("role", role)
        .in_("game_date", dates)
        .execute()
    )
    ohlc_by_date = {row["game_date"]: row for row in ohlc_resp.data or []}

    scoring = _load_scoring()
    batter_rules = scoring["batter"]
    pitcher_rules = scoring["pitcher"]

    # Fetch actual MLB Stats API game logs (actual R/RBI/SB for batters; actual IP/ER/W/L for pitchers)
    first_date = (resp.data or [{}])[0].get("game_date", "")
    season = int(first_date[:4]) if first_date else _date.today().year
    mlb_game_log: dict[int, dict] = {}
    if role == "BATTING":
        mlb_game_log = _fetch_batter_game_log(player_id, season)
    else:
        mlb_game_log = _fetch_pitcher_game_log(player_id, season)

    result = []
    for pk in recent_pks:
        g = games[pk]
        rt_counts: dict[str, int] = {}
        for rt in g["result_types"]:
            rt_counts[rt] = rt_counts.get(rt, 0) + 1

        # Determine opponent team
        ih = (g["inning_half"] or "Top").capitalize()
        if role == "BATTING":
            opponent = g["home_team"] if ih == "Top" else g["away_team"]
        else:
            opponent = g["away_team"] if ih == "Top" else g["home_team"]

        ohlc = ohlc_by_date.get(g["game_date"], {})
        actual = mlb_game_log.get(pk)

        if role == "BATTING":
            if actual:
                pts = _batter_pts_actual(actual, batter_rules)
                stats = {
                    "pa": actual["pa"],
                    "tb": actual["tb"],
                    "hr": actual["hr"],
                    "bb": actual["bb"],
                    "k":  actual["k"],
                }
            else:
                pts = _batter_pts(rt_counts, batter_rules)
                tb = (rt_counts.get("Single", 0) + rt_counts.get("Double", 0) * 2
                      + rt_counts.get("Triple", 0) * 3 + rt_counts.get("HR", 0) * 4)
                stats = {
                    "pa": len(g["result_types"]),
                    "tb": tb,
                    "hr": rt_counts.get("HR", 0),
                    "bb": rt_counts.get("BB", 0) + rt_counts.get("IBB", 0),
                    "k":  rt_counts.get("StrikeOut", 0),
                }
        else:
            if actual:
                pts = _pitcher_pts_actual(actual, pitcher_rules)
                stats = {
                    "ip":  actual["ip"],
                    "h":   actual["h"],
                    "er":  actual["er"],
                    "hr":  actual["hr"],
                    "bb":  actual["bb"],
                    "k":   actual["k"],
                }
            else:
                pts = _pitcher_pts(rt_counts, pitcher_rules)
                outs = (rt_counts.get("OUT", 0) + rt_counts.get("POPUP", 0)
                        + rt_counts.get("GROUNDOUT", 0) + rt_counts.get("StrikeOut", 0))
                h = (rt_counts.get("Single", 0) + rt_counts.get("Double", 0)
                     + rt_counts.get("Triple", 0) + rt_counts.get("HR", 0))
                stats = {
                    "ip":  outs // 3 + (outs % 3) * 0.1,
                    "h":   h,
                    "er":  None,
                    "hr":  rt_counts.get("HR", 0),
                    "bb":  rt_counts.get("BB", 0) + rt_counts.get("IBB", 0),
                    "k":   rt_counts.get("StrikeOut", 0),
                }

        result.append({
            "gamePk": pk,
            "date": g["game_date"],
            "opponent": opponent or "?",
            "elo": round(float(ohlc.get("close") or 0), 1),
            "eloDelta": round(float(ohlc.get("delta") or 0), 1),
            "fantasyPoints": round(pts, 1),
            "stats": stats,
        })

    return {"games": result}


@router.get("/hot-fantasy")
async def hot_fantasy(date: str, role: str = Query("batter")):
    return await _daily_fantasy(date, role, hot=True)


@router.get("/cold-fantasy")
async def cold_fantasy(date: str, role: str = Query("batter")):
    return await _daily_fantasy(date, role, hot=False)


@router.get("/fantasy-leaderboard")
async def fantasy_leaderboard(
    role: str = Query("batter"),
    season: int = Query(2026),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    sb = get_supabase()
    offset = (page - 1) * limit
    fn = "fantasy_batter_leaderboard" if role == "batter" else "fantasy_pitcher_leaderboard"
    resp = sb.rpc(fn, {"p_season": season, "p_limit": limit, "p_offset": offset}).execute()
    pa_key = "total_bf" if role == "pitcher" else "total_pa"
    return [
        {
            "player_id": r["player_id"],
            "full_name": r["full_name"],
            "team": r["team"],
            "position": r["position"],
            "total_pts": round(r["total_pts"], 1),
            "total_pa": r.get(pa_key, 0),
        }
        for r in resp.data or []
    ]


async def _daily_fantasy(date: str, role: str, hot: bool) -> list:
    from collections import defaultdict
    sb = get_supabase()
    id_col = "pitcher_id" if role == "pitcher" else "batter_id"

    all_rows = []
    offset = 0
    while True:
        resp = (
            sb.table("plate_appearances")
            .select(f"{id_col}, result_type")
            .eq("game_date", date)
            .range(offset, offset + 999)
            .execute()
        )
        all_rows.extend(resp.data or [])
        if len(resp.data or []) < 1000:
            break
        offset += 1000

    player_rts: dict[int, dict] = defaultdict(dict)
    for row in all_rows:
        pid = row[id_col]
        rt = row["result_type"]
        player_rts[pid][rt] = player_rts[pid].get(rt, 0) + 1

    scoring = _load_scoring()
    rules = scoring["pitcher" if role == "pitcher" else "batter"]
    pts_fn = _pitcher_pts if role == "pitcher" else _batter_pts
    pts_map = {pid: pts_fn(rt_counts, rules) for pid, rt_counts in player_rts.items()}

    # Initial estimated ranking to identify top/bottom 10 candidates
    sorted_ids = sorted(pts_map, key=lambda p: pts_map[p], reverse=hot)[:10]
    if not sorted_ids:
        return []

    # For batters: refine the top/bottom 10 with actual R/RBI/SB from MLB Stats API
    if role == "batter":
        season = int(date[:4]) if date else _date.today().year
        actual_map = await _fetch_batter_day_stats_batch(sorted_ids, date, season)
        for pid, actual in actual_map.items():
            if actual:
                pts_map[pid] = _batter_pts_actual(actual, rules)
        # Re-sort after actual stats applied
        sorted_ids = sorted(sorted_ids, key=lambda p: pts_map[p], reverse=hot)

    name_resp = (
        sb.table("players")
        .select("player_id, full_name, team, position")
        .in_("player_id", sorted_ids)
        .execute()
    )
    name_map = {r["player_id"]: r for r in name_resp.data or []}

    return [
        {
            "player_id": pid,
            "fantasy_points": round(pts_map[pid], 1),
            "total_pa": sum(player_rts[pid].values()),
            "full_name": name_map.get(pid, {}).get("full_name", f"Player {pid}"),
            "team": name_map.get(pid, {}).get("team", ""),
            "position": name_map.get(pid, {}).get("position", ""),
        }
        for pid in sorted_ids
    ]


@router.get("/players/{player_id}/stat-line")
async def player_stat_line(
    player_id: int,
    role: str = Query("batter"),
    season: int = Query(2026),
):
    """Return season stat line for display in the player profile header."""
    sb = get_supabase()

    # Counting stats from player_season_stats
    ss_resp = (
        sb.table("player_season_stats")
        .select("pa,hits,home_runs,bb,hbp,so,bf,k,er,bb_allowed")
        .eq("player_id", player_id)
        .eq("season_year", season)
        .limit(1)
        .execute()
    )
    ss = ss_resp.data[0] if ss_resp.data else None

    # Advanced stats from player_fangraphs_stats
    fg_resp = (
        sb.table("player_fangraphs_stats")
        .select("xwoba,wrc_plus,war,xfip_minus,siera")
        .eq("player_id", player_id)
        .eq("season_year", season)
        .limit(1)
        .execute()
    )
    fg = fg_resp.data[0] if fg_resp.data else {}

    if not ss:
        return None

    is_pitcher = role == "pitcher"
    pa = ss.get("pa") or 0
    bf = ss.get("bf") or 0

    # Return null if player hasn't played yet
    if (is_pitcher and bf == 0) or (not is_pitcher and pa == 0):
        return None

    def pct(num, denom):
        return round(num / denom, 4) if denom else None

    if is_pitcher:
        k = ss.get("k") or 0
        bb = ss.get("bb_allowed") or 0
        return {
            "bf": bf,
            "k": k,
            "er": ss.get("er") or 0,
            "bb": bb,
            "k_pct": pct(k, bf),
            "bb_pct": pct(bb, bf),
            "k_bb_pct": pct(k - bb, bf),
            "xwoba": fg.get("xwoba"),
            "xfip_minus": fg.get("xfip_minus"),
            "siera": fg.get("siera"),
        }
    else:
        k = ss.get("so") or 0
        bb = (ss.get("bb") or 0) + (ss.get("hbp") or 0)
        return {
            "pa": pa,
            "k": k,
            "h": ss.get("hits") or 0,
            "hr": ss.get("home_runs") or 0,
            "bb": ss.get("bb") or 0,
            "k_pct": pct(k, pa),
            "bb_pct": pct(ss.get("bb") or 0, pa),
            "xwoba": fg.get("xwoba"),
            "wrc_plus": fg.get("wrc_plus"),
            "war": fg.get("war"),
        }


@router.get("/search")
async def search_players(q: str = Query("", min_length=2)):
    sb = get_supabase()
    resp = (
        sb.table("players")
        .select("player_id, full_name, team, position, player_elo(batting_pa, pitching_pa)")
        .ilike("full_name", f"%{q}%")
        .limit(10)
        .execute()
    )
    PITCHER_POSITIONS = {'P', 'SP', 'RP', 'CL', 'MR'}
    results = []
    for row in resp.data:
        elo = row.get("player_elo")
        batting_pa = (elo.get("batting_pa") or 0) if elo else 0
        pitching_pa = (elo.get("pitching_pa") or 0) if elo else 0
        is_two_way = batting_pa > 0 and pitching_pa > 0
        position = row["position"] or ""
        role = "pitcher" if position in PITCHER_POSITIONS else "batter"
        results.append({
            "player_id": row["player_id"],
            "full_name": row["full_name"],
            "team": row["team"],
            "position": position,
            "role": role,
            "is_two_way": is_two_way,
        })
    return results


@router.get("/league-summary")
async def league_summary():
    sb = get_supabase()
    resp = sb.table("player_elo").select("composite_elo").execute()
    players = resp.data or []
    count = len(players)
    avg_elo = round(sum(p["composite_elo"] for p in players) / count) if count else 1500
    elite_count = sum(1 for p in players if p["composite_elo"] >= 1800)
    return {
        "activePlayersCount": count,
        "averageElo": avg_elo,
        "eliteCount": elite_count,
    }


@router.get("/latest-date")
async def latest_date():
    sb = get_supabase()
    resp = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=True)
        .limit(1)
        .execute()
    )
    date = resp.data[0]["game_date"] if resp.data else None
    return {"date": date}


@router.get("/season-meta")
async def season_meta():
    sb = get_supabase()
    earliest = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=False)
        .limit(1)
        .execute()
    )
    latest = (
        sb.table("daily_ohlc")
        .select("game_date")
        .order("game_date", desc=True)
        .limit(1)
        .execute()
    )

    start_date = earliest.data[0]["game_date"] if earliest.data else ""
    end_date = latest.data[0]["game_date"] if latest.data else ""
    year = int(end_date[:4]) if end_date else 2025

    return {"year": year, "startDate": start_date, "endDate": end_date}


# --- Helpers ---

def _flatten_ohlc_player(row: dict) -> dict:
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "game_date": row["game_date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "delta": row["delta"],
        "total_pa": row["total_pa"],
        "full_name": p["full_name"],
        "team": p["team"],
        "position": p["position"],
    }


def _flatten_leaderboard(row: dict) -> dict:
    p = row["players"]
    return {
        "player_id": row["player_id"],
        "composite_elo": row["composite_elo"],
        "batting_elo": row.get("batting_elo") or 1500,
        "pitching_elo": row.get("pitching_elo") or 1500,
        "pa_count": row["pa_count"],
        "batting_pa": row.get("batting_pa") or 0,
        "pitching_pa": row.get("pitching_pa") or 0,
        "last_game_date": row["last_game_date"],
        "full_name": p["full_name"],
        "team": p["team"],
        "position": p["position"],
    }
