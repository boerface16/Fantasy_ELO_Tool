"""Pull current fantasy team roster and free agents from ESPN API.

Updates:
  - current_fantasy_team.md  (Twist and Trout roster)
  - free_agents.csv          (top free agents by position)
"""

import re
from pathlib import Path
import pandas as pd
from espn_api.baseball import League

# ── Auth ──────────────────────────────────────────────────────────────────────
league = League(
    league_id=30294024,
    year=2026,
    espn_s2="AEAU7BdptPDjL%2FjAEYT468VTpbPcinyeOFM4hB2UoLcI8R8hFkd4dPpSY32FdkUc4%2Fo%2FKZdLeuS6EesXRxCQ%2BIm9hjCaG0lcrSU4VpEG5snQoapCOWNY1dINGIx19C9q2qNdXIX3vV%2BN7ZG%2FOfZbA7t%2Bw8ERNMU2y9w%2BqL8DshN95%2BPRST4GwDqBeAEeme%2FPs8mCl0vS8UqE%2FGdQCA8h4Mm96hbh%2FWLrxApiQmL4oxNc78X9ZijHBe3zGGN%2FGpnpfm%2F7hbdR1hWKM2Vxjnr5KzOq",
    swid="{F01945FD-BE32-4BFF-AA41-E08B5ED4F94E}",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEAM_NAME = "Twist and Trout"

# ESPN injury status → display tag
_IL_TAGS = {
    "INJURY_RESERVE": "IL",
    "SIXTY_DAY_IL":   "60-Day IL",
    "TEN_DAY_IL":     "10-Day IL",
    "DAY_TO_DAY":     "DTD",
    "SUSPENSION":     "SUSP",
    "OUT":            "Out",
}

PITCHER_POSITIONS = {"SP", "RP", "P"}


def _il_tag(status: str) -> str | None:
    """Return bracket tag for injury status, or None if active."""
    if not status or status.upper() in ("ACTIVE", "NORMAL", "NA", ""):
        return None
    tag = _IL_TAGS.get(status.upper())
    if tag:
        return tag
    # Fallback: capitalise whatever ESPN sends
    return status.title()


_ESPN_FLEX = {"BE", "BN", "IL", "IL+", "NA", "UTIL", "IF", "MI", "CI", "DL"}
_OF_ALIASES = {"LF", "CF", "RF"}
_PITCHER_POS = {"SP", "RP", "P"}


def _format_positions(player) -> str:
    """Return normalized ESPN eligible positions as '(POS1/POS2/...)'.

    Strips ESPN fantasy-only flex codes (IF, MI, CI, UTIL, BE, etc.),
    maps LF/CF/RF → OF, and deduplicates.
    """
    positions = getattr(player, "eligibleSlots", None) or []
    seen: set[str] = set()
    result: list[str] = []
    for p in positions:
        p = p.strip().upper()
        if not p or p in _ESPN_FLEX:
            continue
        if p in _OF_ALIASES:
            p = "OF"
        if p not in seen:
            seen.add(p)
            result.append(p)
    # For pitchers: if nothing survived, fall back to position code
    if not result:
        pos = (getattr(player, "position", "") or "").upper()
        result = [pos] if pos else []
    return f"({'/'.join(result)})" if result else f"({player.position})"


def _is_pitcher(player) -> bool:
    pos = getattr(player, "position", "") or ""
    return pos.upper() in PITCHER_POSITIONS


def _player_line(player) -> str:
    name = player.name
    team = player.proTeam or "FA"
    pos_str = _format_positions(player)
    tag = _il_tag(getattr(player, "injuryStatus", None) or "")
    line = f"{name} - {team} - {pos_str}"
    if tag:
        line += f" [{tag}]"
    return line


# ── Find my team ──────────────────────────────────────────────────────────────
my_team = next(
    (t for t in league.teams if TEAM_NAME.lower() in t.team_name.lower()),
    None,
)
if my_team is None:
    available = [t.team_name for t in league.teams]
    raise SystemExit(f"Team '{TEAM_NAME}' not found. Available: {available}")

batters = [p for p in my_team.roster if not _is_pitcher(p)]
pitchers = [p for p in my_team.roster if _is_pitcher(p)]

# ── Update current_fantasy_team.md ───────────────────────────────────────────
year = league.year
lines = [
    f"# {my_team.team_name} — Current Roster ({year})\n",
    "\n## Batters\n",
]
for p in batters:
    lines.append(_player_line(p) + "\n")

lines.append("\n## Pitchers\n")
for p in pitchers:
    lines.append(_player_line(p) + "\n")

md_path = REPO_ROOT / "current_fantasy_team.md"
md_path.write_text("".join(lines), encoding="utf-8")
print(f"Updated {md_path}")

# ── Update free_agents.csv ────────────────────────────────────────────────────
fa_list = []
for pos in ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "DH"]:
    for fa in league.free_agents(position=pos, size=100):
        season = fa.stats.get(0, {})
        breakdown = season.get("breakdown", {})
        fa_list.append({
            "Player":            fa.name,
            "Position":          fa.position,
            "MLB_Team":          fa.proTeam,
            "Pct_Owned":         fa.percent_owned,
            "Total_Points":      fa.total_points,
            "Projected_Points":  fa.projected_total_points,
            "Injury_Status":     getattr(fa, "injuryStatus", "") or "",
            "HR":                breakdown.get("HR", 0),
            "RBI":               breakdown.get("RBI", 0),
            "R":                 breakdown.get("R", 0),
            "SB":                breakdown.get("SB", 0),
            "AVG":               breakdown.get("AVG", 0),
            "W":                 breakdown.get("W", 0),
            "ERA":               breakdown.get("ERA", 0),
            "WHIP":              breakdown.get("WHIP", 0),
            "K":                 breakdown.get("K", 0),
            "SV":                breakdown.get("SV", 0),
        })

fa_df = pd.DataFrame(fa_list).drop_duplicates(subset="Player")
fa_path = REPO_ROOT / "free_agents.csv"
fa_df.to_csv(fa_path, index=False)
print(f"Exported {len(fa_df)} free agents → {fa_path}")
