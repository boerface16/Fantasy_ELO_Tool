"""Tests for fangraphs_enricher — MLB Stats API wrapper with daily file cache."""

import os
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.fantasy.fangraphs_enricher import (
    get_batter_stats,
    get_pitcher_stats,
    get_player_stats,
    _cache_path,
    _clean_old_caches,
)


def _mlb_api_response(players: list[dict]) -> dict:
    """Build a minimal MLB Stats API response for the given player dicts."""
    splits = [
        {
            "player": {"id": i + 1, "fullName": p["Name"]},
            "stat": {
                "gamesPlayed": str(p.get("G", 0)),
                "inningsPitched": str(p.get("IP", 0)),
                "saves": str(p.get("SV", 0)),
                "holds": str(p.get("HLD", 0)),
                "stolenBases": str(p.get("SB", 0)),
            },
        }
        for i, p in enumerate(players)
    ]
    return {"stats": [{"totalSplits": len(splits), "splits": splits}]}


MOCK_PITCHERS = [
    {"Name": "Gerrit Cole",    "G": 30, "IP": 180.0, "SV": 0, "HLD": 0, "SB": 0},
    {"Name": "Zack Wheeler",   "G": 28, "IP": 170.0, "SV": 0, "HLD": 0, "SB": 1},
    {"Name": "Corbin Burnes",  "G": 29, "IP": 175.0, "SV": 0, "HLD": 0, "SB": 0},
]


class TestCachePath:
    def test_batting_cache_path(self):
        path = _cache_path("batting", 2025)
        assert "batting_2025_" in path
        assert path.endswith(".parquet")

    def test_pitching_cache_path(self):
        path = _cache_path("pitching", 2025)
        assert "pitching_2025_" in path

    def test_cache_includes_today(self):
        path = _cache_path("batting", 2025)
        assert date.today().isoformat() in path


class TestGetBatterStats:
    def test_returns_empty_dataframe(self):
        """Batter stats are not used — always returns empty DataFrame."""
        df = get_batter_stats(2025)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_returns_dataframe_type(self):
        df = get_batter_stats(2025)
        assert isinstance(df, pd.DataFrame)


class TestGetPitcherStats:
    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_returns_dataframe(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            df = get_pitcher_stats(2025)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_has_expected_columns(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            df = get_pitcher_stats(2025)
        for col in ["Name", "G", "IP", "SV", "HLD", "SB"]:
            assert col in df.columns

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_caches_to_disk(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            get_pitcher_stats(2025)
        parquet_files = [f for f in os.listdir(tmp_path) if f.endswith(".parquet")]
        assert len(parquet_files) == 1

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_reads_from_cache(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            get_pitcher_stats(2025)  # first call — hits API and writes cache
            get_pitcher_stats(2025)  # second call — should read from cache
        assert mock_get.call_count == 1


class TestGetPlayerStats:
    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_pitcher_lookup(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Gerrit Cole", 2025)
        assert result is not None
        assert result["Name"] == "Gerrit Cole"
        assert result["G"] == 30

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_case_insensitive_lookup(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("gerrit cole", 2025)
        assert result is not None
        assert result["Name"] == "Gerrit Cole"

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_missing_player_returns_none(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Fake Player", 2025)
        assert result is None

    @patch("src.fantasy.fangraphs_enricher.requests.get")
    def test_batter_not_in_pitcher_stats(self, mock_get, tmp_path):
        """Position players are not in pitcher stats; get_player_stats returns None."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mlb_api_response(MOCK_PITCHERS)
        mock_get.return_value = mock_resp
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Aaron Judge", 2025)
        assert result is None


class TestCleanOldCaches:
    def test_removes_old_files(self, tmp_path):
        old = tmp_path / "batting_2025_2025-01-01.parquet"
        old.write_text("old")
        today = tmp_path / f"batting_2025_{date.today().isoformat()}.parquet"
        today.write_text("today")

        _clean_old_caches(str(tmp_path), "batting", 2025)

        assert not old.exists()
        assert today.exists()
