"""Tests for elo_lookup — batch Supabase queries with in-memory cache."""

import pytest
from unittest.mock import MagicMock
from src.fantasy.elo_lookup import (
    EloLookup,
    DEFAULT_BATTER_ELO,
    DEFAULT_PITCHER_ELO,
)


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    return client


@pytest.fixture
def sample_talent_data():
    """Simulates Supabase talent_player_current rows."""
    return [
        {"player_id": 1, "player_role": "batter", "talent_type": "contact", "season_elo": 1520.0},
        {"player_id": 1, "player_role": "batter", "talent_type": "power", "season_elo": 1480.0},
        {"player_id": 1, "player_role": "batter", "talent_type": "discipline", "season_elo": 1750.0},
        {"player_id": 2, "player_role": "pitcher", "talent_type": "stuff", "season_elo": 1620.0},
        {"player_id": 2, "player_role": "pitcher", "talent_type": "bip_suppression", "season_elo": 1510.0},
        {"player_id": 2, "player_role": "pitcher", "talent_type": "command", "season_elo": 1700.0},
    ]


class TestEloLookup:

    def test_get_batter_elo(self, mock_supabase, sample_talent_data):
        mock_resp = MagicMock()
        mock_resp.data = [r for r in sample_talent_data if r["player_id"] == 1]
        mock_supabase.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = mock_resp

        lookup = EloLookup(mock_supabase)
        lookup.load_batch([1])
        result = lookup.get_batter_elo(1)

        assert result["contact"] == 1520.0
        assert result["power"] == 1480.0
        assert result["discipline"] == 1750.0

    def test_get_pitcher_elo(self, mock_supabase, sample_talent_data):
        mock_resp = MagicMock()
        mock_resp.data = [r for r in sample_talent_data if r["player_id"] == 2]
        mock_supabase.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = mock_resp

        lookup = EloLookup(mock_supabase)
        lookup.load_batch([2])
        result = lookup.get_pitcher_elo(2)

        assert result["stuff"] == 1620.0
        assert result["bip_suppression"] == 1510.0
        assert result["command"] == 1700.0

    def test_unknown_player_returns_defaults(self, mock_supabase):
        lookup = EloLookup(mock_supabase)
        result = lookup.get_batter_elo(99999)
        assert result == DEFAULT_BATTER_ELO

    def test_unknown_pitcher_returns_defaults(self, mock_supabase):
        lookup = EloLookup(mock_supabase)
        result = lookup.get_pitcher_elo(99999)
        assert result == DEFAULT_PITCHER_ELO

    def test_cache_prevents_duplicate_queries(self, mock_supabase, sample_talent_data):
        mock_resp = MagicMock()
        mock_resp.data = [r for r in sample_talent_data if r["player_id"] == 1]
        mock_supabase.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = mock_resp

        lookup = EloLookup(mock_supabase)
        lookup.load_batch([1])
        lookup.load_batch([1])  # second call should not query again
        # Only one set of queries should have been made
        assert mock_supabase.table.call_count == 2  # batter + pitcher queries

    def test_default_batter_elo_has_required_keys(self):
        for key in ("contact", "power", "discipline"):
            assert key in DEFAULT_BATTER_ELO

    def test_default_pitcher_elo_has_required_keys(self):
        for key in ("stuff", "bip_suppression", "command"):
            assert key in DEFAULT_PITCHER_ELO
