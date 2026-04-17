"""Export detailed speed ELO breakdown for a player to CSV.

Joins MLB Stats API per-game log (SB, CS, 3B, PA) with daily OHLC ELO to show
exactly what each game contributed to speed ELO movement.

Usage:
    python scripts/export_speed_elo.py --player 665862 --season 2026
    python scripts/export_speed_elo.py --player 665862 --season 2026 --out data/speed_elo_665862.csv
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def fetch_player_name(sb, player_id: int) -> str:
    rows = sb.table("players").select("full_name").eq("player_id", player_id).execute().data
    return rows[0]["full_name"] if rows else f"ID {player_id}"


def fetch_current(sb, player_id: int) -> dict | None:
    rows = (
        sb.table("talent_player_current")
        .select("season_elo,career_elo,event_count,pa_count")
        .eq("player_id", player_id)
        .eq("talent_type", "speed")
        .execute()
        .data
    )
    return rows[0] if rows else None


def fetch_ohlc(sb, player_id: int, season: int) -> dict[str, dict]:
    """Return {game_date: ohlc_row} for the season."""
    rows = (
        sb.table("talent_daily_ohlc")
        .select("game_date,open_elo,high_elo,low_elo,close_elo,total_pa")
        .eq("player_id", player_id)
        .eq("talent_type", "speed")
        .eq("elo_type", "SEASON")
        .gte("game_date", f"{season}-01-01")
        .lte("game_date", f"{season}-12-31")
        .order("game_date")
        .execute()
        .data
    ) or []
    return {r["game_date"]: r for r in rows}


def fetch_game_log(player_id: int, season: int) -> list[dict]:
    """Fetch per-game hitting log from MLB Stats API."""
    url = (
        f"{MLB_STATS_BASE}/people/{player_id}/stats"
        f"?stats=gameLog&group=hitting&season={season}&sportId=1"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    splits = data.get("stats", [{}])[0].get("splits", [])
    return splits


def fetch_pa_detail(sb, player_id: int) -> list[dict]:
    """Per-PA speed ELO detail rows joined to plate_appearances for date/event context."""
    detail = (
        sb.table("talent_pa_detail")
        .select("pa_id,elo_before,elo_after,delta")
        .eq("player_id", player_id)
        .eq("talent_type", "speed")
        .eq("player_role", "batter")
        .order("pa_id")
        .execute()
        .data
    ) or []
    if not detail:
        return []
    pa_ids = [r["pa_id"] for r in detail]
    pas = (
        sb.table("plate_appearances")
        .select("pa_id,game_date,result_type,bb_type,on_2b,on_3b")
        .in_("pa_id", pa_ids)
        .execute()
        .data
    ) or []
    pa_map = {r["pa_id"]: r for r in pas}
    for row in detail:
        pa = pa_map.get(row["pa_id"], {})
        row["game_date"] = pa.get("game_date", "")
        row["result_type"] = pa.get("result_type", "")
        row["bb_type"] = pa.get("bb_type", "")
        row["risp"] = pa.get("on_2b", False) or pa.get("on_3b", False)
    return detail


def _elo_driver(sb: int, cs: int, three_b: int, pa_events: list[dict], elo_delta) -> str:
    drivers = []
    if sb:
        drivers.append(f"SBx{sb}" if sb > 1 else "SB")
    if cs:
        drivers.append(f"CSx{cs}" if cs > 1 else "CS")
    if three_b:
        drivers.append(f"3Bx{three_b}" if three_b > 1 else "3B")
    gb_singles = [p for p in pa_events if p.get("bb_type") == "ground_ball"]
    if gb_singles:
        drivers.append("gb_single")
    if not drivers:
        if elo_delta not in ("", 0, "0.0", "+0.0"):
            drivers.append("league_rate_shift")
        else:
            drivers.append("flat")
    return " + ".join(drivers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", type=int, default=665862)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    out_path = args.out or f"data/speed_elo_{args.player}_{args.season}.csv"
    sb = get_supabase()

    name = fetch_player_name(sb, args.player)
    current = fetch_current(sb, args.player)
    ohlc_by_date = fetch_ohlc(sb, args.player, args.season)
    game_log = fetch_game_log(args.player, args.season)
    pa_detail = fetch_pa_detail(sb, args.player)

    # Index PA detail by game_date for inline annotation
    pa_by_date: dict[str, list[dict]] = {}
    for p in pa_detail:
        pa_by_date.setdefault(p["game_date"], []).append(p)

    # Build game-by-game rows
    rows = []
    cum_sb = cum_cs = cum_3b = cum_pa = 0
    prev_elo = None

    for split in game_log:
        date = split["date"]
        s = split["stat"]
        opponent = split.get("opponent", {}).get("abbreviation") or split.get("opponent", {}).get("name", "?")
        is_home = split.get("isHome", True)
        matchup = f"vs {opponent}" if is_home else f"@ {opponent}"

        game_sb  = int(s.get("stolenBases", 0) or 0)
        game_cs  = int(s.get("caughtStealing", 0) or 0)
        game_3b  = int(s.get("triples", 0) or 0)
        game_pa  = int(s.get("plateAppearances", 0) or 0)
        game_hr  = int(s.get("homeRuns", 0) or 0)
        game_h   = int(s.get("hits", 0) or 0)
        game_bb  = int(s.get("baseOnBalls", 0) or 0)

        cum_sb += game_sb
        cum_cs += game_cs
        cum_3b += game_3b
        cum_pa += game_pa

        ohlc = ohlc_by_date.get(date, {})
        close_elo = ohlc.get("close_elo")
        open_elo  = ohlc.get("open_elo")
        high_elo  = ohlc.get("high_elo")
        low_elo   = ohlc.get("low_elo")

        elo_delta = round(close_elo - prev_elo, 2) if (close_elo is not None and prev_elo is not None) else ""
        elo_delta_sign = (f"+{elo_delta}" if isinstance(elo_delta, float) and elo_delta > 0
                          else str(elo_delta) if elo_delta != "" else "")

        # Speed events inline (from PA detail — ground ball singles etc.)
        inline_events = "; ".join(
            f"{p['result_type']}({p['bb_type'] or ''}) elo {p['elo_before']:.1f}->{p['elo_after']:.1f} ({p['delta']:+.2f})"
            for p in pa_by_date.get(date, [])
        )

        rows.append({
            "date": date,
            "matchup": matchup,
            "game_sb": game_sb,
            "game_cs": game_cs,
            "game_3b": game_3b,
            "game_pa": game_pa,
            "game_h": game_h,
            "game_hr": game_hr,
            "game_bb": game_bb,
            "cum_sb": cum_sb,
            "cum_cs": cum_cs,
            "cum_3b": cum_3b,
            "cum_pa": cum_pa,
            "sb_rate_per_600": round(cum_sb / max(cum_pa, 1) * 600, 2),
            "open_elo": round(open_elo, 2) if open_elo is not None else "",
            "high_elo": round(high_elo, 2) if high_elo is not None else "",
            "low_elo": round(low_elo, 2) if low_elo is not None else "",
            "close_elo": round(close_elo, 2) if close_elo is not None else "",
            "elo_delta": elo_delta_sign,
            "elo_driver": _elo_driver(game_sb, game_cs, game_3b, pa_by_date.get(date, []), elo_delta),
            "pa_detail_events": inline_events,
        })

        if close_elo is not None:
            prev_elo = close_elo

    fieldnames = [
        "date", "matchup",
        "game_sb", "game_cs", "game_3b", "game_pa", "game_h", "game_hr", "game_bb",
        "cum_sb", "cum_cs", "cum_3b", "cum_pa", "sb_rate_per_600",
        "open_elo", "high_elo", "low_elo", "close_elo", "elo_delta", "elo_driver",
        "pa_detail_events",
    ]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Player:       {name} ({args.player})")
    if current:
        print(f"Season ELO:   {current['season_elo']:.1f}  (career: {current['career_elo']:.1f})")
        print(f"Events:       {current['event_count']}  |  PA: {current['pa_count']}")
    print(f"Game log:     {len(game_log)} games")
    print(f"OHLC rows:    {len(ohlc_by_date)}")
    print(f"PA detail:    {len(pa_detail)} tracked events")
    print(f"\nExported to:  {out_path}")


if __name__ == "__main__":
    main()
