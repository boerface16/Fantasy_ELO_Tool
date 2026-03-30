"""Tests for fangraphs_enricher — pybaseball wrapper with daily file cache."""

import os
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.fantasy.fangraphs_enricher import (
    get_batter_stats,
    get_pitcher_stats,
    get_player_stats,
    BATTER_COLS,
    PITCHER_COLS,
    _cache_path,
    _clean_old_caches,
)


@pytest.fixture
def mock_batting_df():
    return pd.DataFrame({
        "Name": ["Aaron Judge", "Shohei Ohtani", "Mookie Betts"],
        "Team": ["NYY", "LAD", "LAD"],
        "PA": [600, 650, 580],
        "wRC+": [190, 175, 140],
        "ISO": [0.310, 0.280, 0.220],
        "BB%": [15.2, 12.1, 10.5],
        "K%": [25.0, 22.5, 18.0],
        "wOBA": [0.430, 0.400, 0.365],
        "OPS": [1.050, 0.980, 0.870],
        "AVG": [0.300, 0.290, 0.275],
        "SLG": [0.600, 0.560, 0.490],
    })


@pytest.fixture
def mock_pitching_df():
    return pd.DataFrame({
        "Name": ["Gerrit Cole", "Zack Wheeler", "Corbin Burnes"],
        "Team": ["NYY", "PHI", "AZ"],
        "IP": [200.0, 195.0, 190.0],
        "ERA": [2.80, 3.10, 3.25],
        "FIP": [2.90, 3.00, 3.15],
        "WHIP": [1.05, 1.10, 1.12],
        "K/9": [10.5, 9.8, 9.5],
        "BB/9": [2.1, 2.3, 2.5],
        "ERA-": [72, 80, 84],
        "H/9": [7.0, 7.5, 7.8],
        "HR/9": [0.9, 1.0, 1.1],
    })


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
    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    def test_returns_dataframe(self, mock_bs, mock_batting_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            df = get_batter_stats(2025)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    def test_filters_columns(self, mock_bs, mock_batting_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            df = get_batter_stats(2025)
        for col in BATTER_COLS:
            if col in mock_batting_df.columns:
                assert col in df.columns

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    def test_caches_to_disk(self, mock_bs, mock_batting_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            get_batter_stats(2025)
        parquet_files = [f for f in os.listdir(tmp_path) if f.endswith(".parquet")]
        assert len(parquet_files) == 1

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    def test_reads_from_cache(self, mock_bs, mock_batting_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            get_batter_stats(2025)  # first call writes cache
            get_batter_stats(2025)  # second call reads from cache
        assert mock_bs.call_count == 1


class TestGetPitcherStats:
    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_returns_dataframe(self, mock_ps, mock_pitching_df, tmp_path):
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            df = get_pitcher_stats(2025)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_caches_to_disk(self, mock_ps, mock_pitching_df, tmp_path):
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            get_pitcher_stats(2025)
        parquet_files = [f for f in os.listdir(tmp_path) if f.endswith(".parquet")]
        assert len(parquet_files) == 1


class TestGetPlayerStats:
    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_batter_lookup(self, mock_ps, mock_bs, mock_batting_df, mock_pitching_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Aaron Judge", 2025)
        assert result is not None
        assert result["Name"] == "Aaron Judge"
        assert result["wRC+"] == 190

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_pitcher_lookup(self, mock_ps, mock_bs, mock_batting_df, mock_pitching_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Gerrit Cole", 2025)
        assert result is not None
        assert result["Name"] == "Gerrit Cole"
        assert result["ERA"] == 2.80

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_missing_player(self, mock_ps, mock_bs, mock_batting_df, mock_pitching_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("Fake Player", 2025)
        assert result is None

    @patch("src.fantasy.fangraphs_enricher.batting_stats")
    @patch("src.fantasy.fangraphs_enricher.pitching_stats")
    def test_fuzzy_match(self, mock_ps, mock_bs, mock_batting_df, mock_pitching_df, tmp_path):
        mock_bs.return_value = mock_batting_df
        mock_ps.return_value = mock_pitching_df
        with patch("src.fantasy.fangraphs_enricher.CACHE_DIR", str(tmp_path)):
            result = get_player_stats("aaron judge", 2025)  # lowercase
        assert result is not None
        assert result["Name"] == "Aaron Judge"


class TestCleanOldCaches:
    def test_removes_old_files(self, tmp_path):
        # Create old cache files
        old = tmp_path / "batting_2025_2025-01-01.parquet"
        old.write_text("old")
        today = tmp_path / f"batting_2025_{date.today().isoformat()}.parquet"
        today.write_text("today")

        _clean_old_caches(str(tmp_path), "batting", 2025)

        assert not old.exists()
        assert today.exists()
