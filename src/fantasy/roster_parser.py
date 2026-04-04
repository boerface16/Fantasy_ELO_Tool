"""Parse pasted ESPN roster text into structured entries.

Handles multiple formats:
- ESPN paste: "C\tSalvador Perez, KC C"
- Simple names: "Aaron Judge" (one per line)
- CSV: "C,Salvador Perez,KC"
"""

import re
from dataclasses import dataclass

VALID_SLOTS = {
    "C", "1B", "2B", "3B", "SS", "OF", "DH", "UTIL",
    "SP", "RP", "P",
    "Bench", "BE", "IL", "IL+", "DL", "NA",
}

MLB_TEAMS = {
    "AZ", "ATL", "BAL", "BOS", "CHC", "CWS", "CIN", "CLE",
    "COL", "DET", "HOU", "KC", "LAA", "LAD", "MIA", "MIL",
    "MIN", "NYM", "NYY", "ATH", "OAK", "PHI", "PIT", "SD",
    "SF", "SEA", "STL", "TB", "TEX", "TOR", "WSH",
}

# Case-insensitive lookup for team abbreviations
_TEAM_LOOKUP = {t.upper(): t for t in MLB_TEAMS}

SECTION_HEADERS = {"BATTERS", "PITCHERS", "BENCH", "HITTERS", "STARTERS", "RELIEVERS"}

POSITION_TAGS = {
    "C", "1B", "2B", "3B", "SS", "OF", "DH", "SP", "RP", "P", "LF", "CF", "RF",
}


@dataclass
class RosterEntry:
    slot: str       # lineup slot (C, 1B, SP, Bench, IL, etc.)
    name: str       # player full name
    team: str       # MLB team abbreviation (or "" if unknown)
    player_id: int | None = None   # DB player_id (set during enrichment)
    position: str | None = None    # DB position code (SP, RP, C, etc.)


def parse_roster_text(text: str) -> list[RosterEntry]:
    """Parse roster text into RosterEntry list.

    Handles ESPN paste format, simple name lists, and CSV format.
    """
    if not text or not text.strip():
        return []

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    entries = []

    for line in lines:
        entry = _parse_line(line)
        if entry:
            entries.append(entry)

    return entries


def _parse_line(line: str) -> RosterEntry | None:
    """Parse a single line into a RosterEntry."""
    # Skip section headers
    if line.strip().upper() in SECTION_HEADERS:
        return None

    # Try dash-separated format: "H. Goodman - Col - (C/DH)"
    dash_result = _parse_dash_separated(line)
    if dash_result:
        return dash_result

    # Try tab-separated ESPN format: "C\tSalvador Perez, KC C"
    if "\t" in line:
        return _parse_espn_tab(line)

    # Try CSV format: "C,Salvador Perez,KC"
    if line.count(",") >= 2:
        return _parse_csv(line)

    # Try "SLOT  Name, TEAM POS" with spaces
    match = re.match(r'^(C|1B|2B|3B|SS|OF|DH|UTIL|SP|RP|P|Bench|BE|IL|IL\+|DL|NA)\s+(.+)', line, re.IGNORECASE)
    if match:
        slot = _normalize_slot(match.group(1))
        return _parse_player_info(slot, match.group(2).strip())

    # Simple name (no slot)
    name = line.strip()
    if name and not name.startswith("#"):
        # Strip trailing team/position tags
        cleaned = _extract_name_and_team(name)
        if cleaned:
            return RosterEntry(slot="", name=cleaned[0], team=cleaned[1])

    return None


def _parse_dash_separated(line: str) -> RosterEntry | None:
    """Parse dash-separated format: 'H. Goodman - Col - (C/DH)' or 'T. Glasnow - LAD -(SP)'."""
    # Must have at least one dash to qualify
    if "-" not in line:
        return None

    # Extract parenthesized position(s) like (C/DH), (SP), (2B/3B)
    pos_match = re.search(r'\(([^)]+)\)', line)
    if not pos_match:
        return None

    positions = pos_match.group(1)
    # Use the first position as the slot
    slot = positions.split("/")[0].strip()
    if slot.upper() not in {p.upper() for p in POSITION_TAGS}:
        return None

    # Remove the position portion and split by dashes
    remainder = line[:pos_match.start()].strip().rstrip("-").strip()
    parts = [p.strip() for p in remainder.split("-") if p.strip()]

    if len(parts) < 2:
        return None

    # Last part is team, everything before is the name
    team_raw = parts[-1].strip()
    team = _normalize_team(team_raw)
    name = " - ".join(parts[:-1]).strip() if len(parts) > 2 else parts[0].strip()

    if not name:
        return None

    return RosterEntry(slot=slot.upper(), name=name, team=team)


def _parse_espn_tab(line: str) -> RosterEntry | None:
    """Parse ESPN tab-separated: 'C\tSalvador Perez, KC C'."""
    parts = line.split("\t", 1)
    if len(parts) != 2:
        return None

    slot = _normalize_slot(parts[0].strip())
    return _parse_player_info(slot, parts[1].strip())


def _parse_csv(line: str) -> RosterEntry | None:
    """Parse CSV: 'C,Salvador Perez,KC'."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None

    first = parts[0].upper()
    if first in VALID_SLOTS or first in {"BE"}:
        slot = _normalize_slot(first)
        name = parts[1]
        team = _normalize_team(parts[2]) if len(parts) > 2 else ""
        return RosterEntry(slot=slot, name=name, team=team)

    # No slot prefix — treat as "name, team, ..."
    name = parts[0]
    team = _normalize_team(parts[1])
    return RosterEntry(slot="", name=name, team=team)


def _parse_player_info(slot: str, info: str) -> RosterEntry | None:
    """Parse player info string like 'Salvador Perez, KC C' or 'Aaron Judge'."""
    result = _extract_name_and_team(info)
    if result:
        return RosterEntry(slot=slot, name=result[0], team=result[1])
    return None


def _extract_name_and_team(info: str) -> tuple[str, str] | None:
    """Extract (name, team) from 'Salvador Perez, KC C' or 'Aaron Judge'."""
    if not info.strip():
        return None

    # Pattern: "Name, TEAM POS[, POS]"
    match = re.match(r'^(.+?),\s*([A-Za-z]{2,3})\s+(.*)$', info)
    if match:
        name = match.group(1).strip()
        team = _normalize_team(match.group(2))
        if team:
            return (name, team)

    # Pattern: "Name, TEAM"
    match = re.match(r'^(.+?),\s*([A-Za-z]{2,3})\s*$', info)
    if match:
        name = match.group(1).strip()
        team = _normalize_team(match.group(2))
        if team:
            return (name, team)

    # Just a name — strip any trailing position tags
    name = info.strip()
    # Remove trailing position-like words
    name = re.sub(r'\s+(C|1B|2B|3B|SS|OF|DH|SP|RP|P|LF|CF|RF)(\s*,\s*(C|1B|2B|3B|SS|OF|DH|SP|RP|P|LF|CF|RF))*\s*$', '', name)
    name = name.strip().rstrip(",").strip()
    if name:
        return (name, "")
    return None


def _normalize_team(team_raw: str) -> str:
    """Case-insensitive team abbreviation lookup."""
    return _TEAM_LOOKUP.get(team_raw.strip().upper(), "")


def _normalize_slot(slot: str) -> str:
    """Normalize slot names."""
    slot = slot.strip()
    if slot.upper() == "BE":
        return "Bench"
    if slot in VALID_SLOTS:
        return slot
    # Try case-insensitive match
    for valid in VALID_SLOTS:
        if slot.upper() == valid.upper():
            return valid
    return slot
