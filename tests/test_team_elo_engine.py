"""TDD tests for the FiveThirtyEight-style Team ELO Engine."""

import pytest
from datetime import date
from math import log

from src.engine.team_elo_engine import (
    TeamEloEngine,
    GameResult,
    TeamEloRecord,
    extract_game_results,
)


@pytest.fixture
def config():
    return {
        "initial_elo": 1500.0,
        "k_factor": 4.0,
        "home_field_advantage": 24.0,
        "season_regression_fraction": 0.333,
        "elo_divisor": 400.0,
    }


@pytest.fixture
def engine(config):
    return TeamEloEngine(config)


def make_game(home="NYY", away="BOS", home_score=5, away_score=3,
              game_date=date(2025, 6, 15), game_pk=100001):
    return GameResult(
        game_pk=game_pk,
        game_date=game_date,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
    )


class TestInitialization:
    def test_new_teams_start_at_initial_elo(self, engine):
        game = make_game()
        home_rec, away_rec = engine.process_game(game)
        assert home_rec.elo_before == 1500.0
        assert away_rec.elo_before == 1500.0

    def test_engine_starts_with_empty_ratings(self, engine):
        assert len(engine.ratings) == 0
        assert len(engine.records) == 0


class TestZeroSum:
    def test_winner_gain_equals_loser_loss(self, engine):
        game = make_game(home_score=5, away_score=3)
        home_rec, away_rec = engine.process_game(game)

        home_delta = home_rec.elo_after - home_rec.elo_before
        away_delta = away_rec.elo_after - away_rec.elo_before
        assert abs(home_delta + away_delta) < 1e-10

    def test_zero_sum_across_many_games(self, engine):
        games = [
            make_game("NYY", "BOS", 5, 3, date(2025, 6, 1), 1001),
            make_game("BOS", "NYY", 2, 1, date(2025, 6, 2), 1002),
            make_game("LAD", "SF",  7, 2, date(2025, 6, 1), 1003),
            make_game("SF",  "LAD", 4, 3, date(2025, 6, 2), 1004),
        ]
        engine.process_season(games)

        total_deviation = sum(elo - 1500.0 for elo in engine.ratings.values())
        assert abs(total_deviation) < 1e-8


class TestHomeFieldAdvantage:
    def test_equal_teams_home_expected_greater_than_half(self, engine):
        # Two 1500-rated teams: home should have > 50% expected
        expected = engine._expected_score(1500.0 + 24.0, 1500.0)
        assert expected > 0.5

    def test_home_team_gains_less_when_winning(self, engine):
        """Home team is favored, so winning yields a smaller gain than the
        away team would get for the same margin."""
        game_home_wins = make_game("NYY", "BOS", 3, 2, date(2025, 6, 1), 1001)
        home_rec, _ = engine.process_game(game_home_wins)
        home_gain = home_rec.elo_after - home_rec.elo_before

        engine2 = TeamEloEngine(engine._config)
        game_away_wins = make_game("NYY", "BOS", 2, 3, date(2025, 6, 1), 1002)
        _, away_rec = engine2.process_game(game_away_wins)
        away_gain = away_rec.elo_after - away_rec.elo_before

        # Away team gains more for winning (upset vs expectation)
        assert away_gain > home_gain


class TestMOVMultiplier:
    def test_one_run_game(self, engine):
        mov = engine._mov_multiplier(1)
        assert abs(mov - log(2)) < 1e-10

    def test_five_run_game(self, engine):
        mov = engine._mov_multiplier(5)
        assert abs(mov - log(6)) < 1e-10

    def test_diminishing_returns(self, engine):
        """Going from 1→2 run diff should add more MOV than going from 5→6."""
        diff_1_to_2 = engine._mov_multiplier(2) - engine._mov_multiplier(1)
        diff_5_to_6 = engine._mov_multiplier(6) - engine._mov_multiplier(5)
        assert diff_1_to_2 > diff_5_to_6

    def test_blowout_earns_more_than_squeaker(self, engine):
        game_close = make_game(home_score=3, away_score=2, game_pk=1001)
        game_blowout = make_game(home_score=10, away_score=2, game_pk=1002)

        home_close, _ = engine.process_game(game_close)
        close_gain = home_close.elo_after - home_close.elo_before

        engine2 = TeamEloEngine(engine._config)
        home_blowout, _ = engine2.process_game(game_blowout)
        blowout_gain = home_blowout.elo_after - home_blowout.elo_before

        assert blowout_gain > close_gain


class TestSeasonReset:
    def test_ratings_regress_toward_mean(self, engine):
        # Set up a team at 1600 (above mean)
        engine.ratings["NYY"] = 1600.0
        engine.ratings["BOS"] = 1400.0
        engine._current_season = 2025

        engine._season_reset(2026)

        # NYY should be closer to 1500 by 1/3
        assert abs(engine.ratings["NYY"] - (1600 + 0.333 * (1500 - 1600))) < 1e-6
        assert abs(engine.ratings["BOS"] - (1400 + 0.333 * (1500 - 1400))) < 1e-6

    def test_reset_triggered_on_year_change(self, engine):
        game_2025 = make_game(home_score=5, away_score=3, game_date=date(2025, 9, 28), game_pk=1001)
        engine.process_game(game_2025)

        nyy_before_reset = engine.ratings["NYY"]
        bos_before_reset = engine.ratings["BOS"]

        game_2026 = make_game(home_score=4, away_score=2, game_date=date(2026, 3, 27), game_pk=1002)
        engine.process_game(game_2026)

        # The 2026 game's elo_before should reflect the regressed value, not the raw 2025 value
        rec_2026_home = engine.records[2]  # 3rd record (index 2) is home team in 2nd game
        expected_regressed = nyy_before_reset + 0.333 * (1500.0 - nyy_before_reset)
        assert abs(rec_2026_home.elo_before - expected_regressed) < 0.01


class TestUpsetBonus:
    def test_underdog_gains_more(self, engine):
        """A weaker team beating a stronger team gains more ELO."""
        engine.ratings["STRONG"] = 1600.0
        engine.ratings["WEAK"] = 1400.0
        engine._current_season = 2025

        # Weak team (away) beats strong team (home) — big upset
        game = make_game("STRONG", "WEAK", 2, 3, date(2025, 7, 1), 2001)
        _, away_rec = engine.process_game(game)
        upset_gain = away_rec.elo_after - away_rec.elo_before

        engine2 = TeamEloEngine(engine._config)
        engine2.ratings["STRONG"] = 1600.0
        engine2.ratings["WEAK"] = 1400.0
        engine2._current_season = 2025

        # Strong team (home) beats weak team (away) — expected result
        game2 = make_game("STRONG", "WEAK", 3, 2, date(2025, 7, 1), 2002)
        home_rec, _ = engine2.process_game(game2)
        expected_gain = home_rec.elo_after - home_rec.elo_before

        assert upset_gain > expected_gain


class TestExtractGameResults:
    def test_bottom_inning_last_pa(self):
        """Home team batting in bottom inning: bat_score=home, fld_score=away."""
        pa_rows = [
            {"pa_id": 1, "game_pk": 100, "game_date": "2025-06-15",
             "home_team": "NYY", "away_team": "BOS",
             "bat_score": 0, "fld_score": 0, "inning_half": "Top"},
            {"pa_id": 2, "game_pk": 100, "game_date": "2025-06-15",
             "home_team": "NYY", "away_team": "BOS",
             "bat_score": 3, "fld_score": 5, "inning_half": "Bot"},
        ]
        results = extract_game_results(pa_rows)
        assert len(results) == 1
        game = results[0]
        # Bot inning: bat_score=home=3, fld_score=away=5
        assert game.home_team == "NYY"
        assert game.home_score == 3
        assert game.away_score == 5

    def test_top_inning_last_pa(self):
        """Away team batting in top inning: bat_score=away, fld_score=home."""
        pa_rows = [
            {"pa_id": 1, "game_pk": 200, "game_date": "2025-06-15",
             "home_team": "LAD", "away_team": "SF",
             "bat_score": 0, "fld_score": 0, "inning_half": "Bot"},
            {"pa_id": 5, "game_pk": 200, "game_date": "2025-06-15",
             "home_team": "LAD", "away_team": "SF",
             "bat_score": 2, "fld_score": 7, "inning_half": "Top"},
        ]
        results = extract_game_results(pa_rows)
        assert len(results) == 1
        game = results[0]
        # Top inning: bat_score=away=2, fld_score=home=7
        assert game.home_score == 7
        assert game.away_score == 2

    def test_multiple_games(self):
        pa_rows = [
            {"pa_id": 1, "game_pk": 100, "game_date": "2025-06-15",
             "home_team": "NYY", "away_team": "BOS",
             "bat_score": 4, "fld_score": 3, "inning_half": "Bot"},
            {"pa_id": 2, "game_pk": 200, "game_date": "2025-06-15",
             "home_team": "LAD", "away_team": "SF",
             "bat_score": 1, "fld_score": 6, "inning_half": "Top"},
        ]
        results = extract_game_results(pa_rows)
        assert len(results) == 2

    def test_chronological_sort(self):
        pa_rows = [
            {"pa_id": 10, "game_pk": 200, "game_date": "2025-06-16",
             "home_team": "LAD", "away_team": "SF",
             "bat_score": 3, "fld_score": 2, "inning_half": "Bot"},
            {"pa_id": 5, "game_pk": 100, "game_date": "2025-06-15",
             "home_team": "NYY", "away_team": "BOS",
             "bat_score": 4, "fld_score": 3, "inning_half": "Bot"},
        ]
        results = extract_game_results(pa_rows)
        assert results[0].game_date < results[1].game_date


class TestBatchProcessing:
    def test_ten_games_produce_twenty_records(self, engine):
        games = [
            make_game("NYY", "BOS", 5, 3, date(2025, 6, d), 1000 + d)
            for d in range(1, 11)
        ]
        records = engine.process_season(games)
        assert len(records) == 20

    def test_ratings_diverge_after_season(self, engine):
        # NYY wins every game at home
        games = [
            make_game("NYY", "BOS", 5, 3, date(2025, 6, d), 1000 + d)
            for d in range(1, 11)
        ]
        engine.process_season(games)

        assert engine.ratings["NYY"] > 1500.0
        assert engine.ratings["BOS"] < 1500.0

    def test_record_fields_populated(self, engine):
        game = make_game("NYY", "BOS", 5, 3)
        home_rec, away_rec = engine.process_game(game)

        assert home_rec.team_code == "NYY"
        assert home_rec.opponent_code == "BOS"
        assert home_rec.result == "W"
        assert home_rec.run_diff == 2
        assert home_rec.game_pk == 100001

        assert away_rec.team_code == "BOS"
        assert away_rec.opponent_code == "NYY"
        assert away_rec.result == "L"
        assert away_rec.run_diff == -2
        assert away_rec.game_pk == 100001
