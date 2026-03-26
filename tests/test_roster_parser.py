"""Tests for roster_parser — parse pasted ESPN roster text, fuzzy-match to DB players."""

import pytest
from src.fantasy.roster_parser import parse_roster_text, RosterEntry


# --- Sample roster formats ---

ESPN_PASTE = """C	Salvador Perez, KC C
1B	Vladimir Guerrero Jr., TOR 1B
2B	Marcus Semien, TEX 2B, SS
3B	Manny Machado, SD 3B
SS	Trea Turner, PHI SS
OF	Aaron Judge, NYY OF
OF	Kyle Tucker, CHC OF
OF	Jarren Duran, BOS OF
UTIL	Shohei Ohtani, LAD DH
SP	Zack Wheeler, PHI SP
SP	Corbin Burnes, AZ SP
SP	Logan Webb, SF SP
RP	Ryan Helsley, STL RP
Bench	Gunnar Henderson, BAL SS
Bench	Josh Naylor, AZ 1B
IL	Mike Trout, LAA OF"""

SIMPLE_NAMES = """Aaron Judge
Shohei Ohtani
Manny Machado"""

CSV_FORMAT = """C,Salvador Perez,KC
1B,Vladimir Guerrero Jr.,TOR
SS,Trea Turner,PHI"""


class TestParseRosterText:

    def test_espn_paste_count(self):
        entries = parse_roster_text(ESPN_PASTE)
        assert len(entries) == 16

    def test_espn_paste_positions(self):
        entries = parse_roster_text(ESPN_PASTE)
        slots = [e.slot for e in entries]
        assert slots[0] == "C"
        assert slots[5] == "OF"
        assert slots[9] == "SP"
        assert slots[15] == "IL"

    def test_espn_paste_names(self):
        entries = parse_roster_text(ESPN_PASTE)
        names = [e.name for e in entries]
        assert "Salvador Perez" in names
        assert "Aaron Judge" in names
        assert "Shohei Ohtani" in names

    def test_espn_paste_teams(self):
        entries = parse_roster_text(ESPN_PASTE)
        team_map = {e.name: e.team for e in entries}
        assert team_map["Aaron Judge"] == "NYY"
        assert team_map["Trea Turner"] == "PHI"

    def test_simple_names(self):
        entries = parse_roster_text(SIMPLE_NAMES)
        assert len(entries) == 3
        names = [e.name for e in entries]
        assert "Aaron Judge" in names

    def test_csv_format(self):
        entries = parse_roster_text(CSV_FORMAT)
        assert len(entries) == 3
        assert entries[0].name == "Salvador Perez"

    def test_empty_input(self):
        entries = parse_roster_text("")
        assert entries == []

    def test_whitespace_only(self):
        entries = parse_roster_text("   \n\n  \n")
        assert entries == []

    def test_il_players_marked(self):
        entries = parse_roster_text(ESPN_PASTE)
        il_entries = [e for e in entries if e.slot == "IL"]
        assert len(il_entries) == 1
        assert il_entries[0].name == "Mike Trout"

    def test_multi_position_player(self):
        """Marcus Semien listed as '2B, SS' should still parse correctly."""
        entries = parse_roster_text(ESPN_PASTE)
        semien = [e for e in entries if "Semien" in e.name][0]
        assert semien.slot == "2B"
        assert semien.team == "TEX"

    def test_roster_entry_fields(self):
        entries = parse_roster_text(ESPN_PASTE)
        entry = entries[0]
        assert hasattr(entry, "slot")
        assert hasattr(entry, "name")
        assert hasattr(entry, "team")
