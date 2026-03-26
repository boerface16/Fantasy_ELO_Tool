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

POSITION_TAGS = {
    "C", "1B", "2B", "3B", "SS", "OF", "DH", "SP", "RP", "P", "LF", "CF", "RF",
}


@dataclass
class RosterEntry:
    slot: str       # lineup slot (C, 1B, SP, Bench, IL, etc.)
    name: str       # player full name
    team: str       # MLB team abbreviation (or "" if unknown)


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
        team = parts[2] if len(parts) > 2 and parts[2].upper() in MLB_TEAMS else ""
        return RosterEntry(slot=slot, name=name, team=team)

    # No slot prefix — treat as "name, team, ..."
    name = parts[0]
    team = parts[1].upper() if parts[1].upper() in MLB_TEAMS else ""
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
    match = re.match(r'^(.+?),\s*([A-Z]{2,3})\s+(.*)$', info)
    if match:
        name = match.group(1).strip()
        team = match.group(2).strip()
        if team in MLB_TEAMS:
            return (name, team)

    # Pattern: "Name, TEAM"
    match = re.match(r'^(.+?),\s*([A-Z]{2,3})\s*$', info)
    if match:
        name = match.group(1).strip()
        team = match.group(2).strip()
        if team in MLB_TEAMS:
            return (name, team)

    # Just a name — strip any trailing position tags
    name = info.strip()
    # Remove trailing position-like words
    name = re.sub(r'\s+(C|1B|2B|3B|SS|OF|DH|SP|RP|P|LF|CF|RF)(\s*,\s*(C|1B|2B|3B|SS|OF|DH|SP|RP|P|LF|CF|RF))*\s*$', '', name)
    name = name.strip().rstrip(",").strip()
    if name:
        return (name, "")
    return None


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
