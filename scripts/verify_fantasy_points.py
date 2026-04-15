"""Compare our leaderboard fantasy points against ESPN's actual totals.

Usage:
    python scripts/verify_fantasy_points.py

Reads:
    data/free_agents.csv  (exported by ESPN_API.py)

Queries:
    Supabase fantasy_batter_leaderboard() and fantasy_pitcher_leaderboard() RPCs

Outputs:
    - Per-player comparison table sorted by absolute delta
    - Mean absolute error for batters and pitchers
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SEASON = 2026
FREE_AGENTS_PATH = "data/free_agents.csv"

PITCHER_POSITIONS = {"SP", "RP", "P"}


def get_supabase():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def fetch_our_leaderboard(sb) -> pd.DataFrame:
    """Pull all batter + pitcher rows from our leaderboard RPCs."""
    batter_rows = sb.rpc(
        "fantasy_batter_leaderboard",
        {"p_season": SEASON, "p_limit": 2000, "p_offset": 0},
    ).execute().data

    pitcher_rows = sb.rpc(
        "fantasy_pitcher_leaderboard",
        {"p_season": SEASON, "p_limit": 2000, "p_offset": 0},
    ).execute().data

    batters = pd.DataFrame(batter_rows)[["full_name", "team", "total_pts"]].copy()
    batters["role"] = "batter"
    batters.rename(columns={"total_pts": "our_pts"}, inplace=True)

    pitchers = pd.DataFrame(pitcher_rows)[["full_name", "team", "total_pts"]].copy()
    pitchers["role"] = "pitcher"
    pitchers.rename(columns={"total_pts": "our_pts"}, inplace=True)

    return pd.concat([batters, pitchers], ignore_index=True)


def load_espn_data() -> pd.DataFrame:
    df = pd.read_csv(FREE_AGENTS_PATH)
    df["role"] = df["Position"].apply(
        lambda p: "pitcher" if p in PITCHER_POSITIONS else "batter"
    )
    # Normalize team names: ESPN uses mixed case (e.g., "ChW"), normalise to upper
    df["MLB_Team"] = df["MLB_Team"].str.upper()
    return df[["Player", "MLB_Team", "role", "Total_Points", "Projected_Points"]].copy()


def normalize_name(name: str) -> str:
    """Lowercase + strip for fuzzy matching."""
    return name.lower().strip()


def main():
    if not os.path.exists(FREE_AGENTS_PATH):
        sys.exit(f"ERROR: {FREE_AGENTS_PATH} not found. Run scripts/ESPN_API.py first.")

    print("Loading ESPN data...")
    espn = load_espn_data()
    # Only players with nonzero ESPN points (otherwise comparison is noise)
    espn = espn[espn["Total_Points"] > 0].copy()
    print(f"  {len(espn)} ESPN players with Total_Points > 0")

    print("Fetching our leaderboard from Supabase...")
    sb = get_supabase()
    ours = fetch_our_leaderboard(sb)
    print(f"  {len(ours)} players in our leaderboard")

    # Build name lookup from our data
    ours["name_key"] = ours["full_name"].apply(normalize_name)
    espn["name_key"] = espn["Player"].apply(normalize_name)

    merged = espn.merge(ours, on="name_key", how="inner")
    merged["delta"] = merged["our_pts"] - merged["Total_Points"]
    merged["abs_delta"] = merged["delta"].abs()

    print(f"\n  Matched {len(merged)} players ({len(espn) - len(merged)} ESPN-only, no match in our DB)\n")

    # ── Batter report ─────────────────────────────────────────────────────────
    batters = merged[merged["role_x"] == "batter"].copy()
    pitchers = merged[merged["role_x"] == "pitcher"].copy()

    def report(label: str, df: pd.DataFrame):
        if df.empty:
            print(f"No {label} data to report.")
            return
        mae = df["abs_delta"].mean()
        print(f"{'='*60}")
        print(f"{label.upper()}  —  n={len(df)}  MAE={mae:.1f} pts")
        print(f"{'='*60}")
        top = df.nlargest(20, "abs_delta")[
            ["Player", "MLB_Team", "Total_Points", "our_pts", "delta"]
        ]
        top.columns = ["Player", "Team", "ESPN", "Ours", "Delta"]
        print(top.to_string(index=False))
        print()

        # Systematic bias
        mean_delta = df["delta"].mean()
        print(f"  Mean delta (Ours - ESPN): {mean_delta:+.1f}  "
              f"({'we over-count' if mean_delta > 0 else 'we under-count'})")
        print()

    report("batters", batters)
    report("pitchers", pitchers)


if __name__ == "__main__":
    main()
