"""FiveThirtyEight-style Team ELO Engine.

Rates all 30 MLB teams based on game results. Each team starts at 1500.
Zero-sum updates with home field advantage and margin-of-victory scaling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log


@dataclass
class GameResult:
    """One completed MLB game, deduced from plate_appearances."""

    game_pk: int
    game_date: date
    home_team: str
    away_team: str
    home_score: int
    away_score: int


@dataclass
class TeamEloRecord:
    """One row destined for the team_elo Supabase table."""

    team_code: str
    game_date: str  # ISO date string
    game_pk: int
    elo_before: float
    elo_after: float
    opponent_code: str
    result: str  # 'W' or 'L'
    run_diff: int


class TeamEloEngine:
    """FiveThirtyEight-style team ELO calculator.

    Config keys: initial_elo, k_factor, home_field_advantage,
                 season_regression_fraction, elo_divisor.
    """

    # FiveThirtyEight-style reset weights
    PROJECTION_WEIGHT = 0.67
    PRIOR_SEASON_WEIGHT = 0.33
    # ELO points per win above .500 (~10 ELO per win is standard)
    ELO_PER_WIN = 10.0

    def __init__(self, config: dict, projected_wins: dict[str, float] | None = None):
        self._config = config
        self.initial_elo: float = config["initial_elo"]
        self.k: float = config["k_factor"]
        self.hfa: float = config["home_field_advantage"]
        self.regression: float = config["season_regression_fraction"]
        self.divisor: float = config["elo_divisor"]
        self.ratings: dict[str, float] = {}
        self.records: list[TeamEloRecord] = []
        self._current_season: int | None = None
        self._projected_wins: dict[str, float] = projected_wins or {}

    def _get_elo(self, team: str) -> float:
        return self.ratings.setdefault(team, self.initial_elo)

    def _expected_score(self, team_elo: float, opp_elo: float) -> float:
        return 1.0 / (1.0 + 10 ** ((opp_elo - team_elo) / self.divisor))

    def _mov_multiplier(self, run_diff: int) -> float:
        return log(abs(run_diff) + 1)

    def _season_reset(self, new_season: int) -> None:
        """FiveThirtyEight-style reset: 67% projection + 33% regressed prior."""
        for team in self.ratings:
            # Regress prior season final rating 1/3 toward mean
            regressed = self.ratings[team] + self.regression * (
                self.initial_elo - self.ratings[team]
            )
            # If we have projected wins, blend with projection
            if team in self._projected_wins:
                proj_wins = self._projected_wins[team]
                proj_elo = self.initial_elo + (proj_wins - 81) * self.ELO_PER_WIN
                self.ratings[team] = (
                    self.PROJECTION_WEIGHT * proj_elo
                    + self.PRIOR_SEASON_WEIGHT * regressed
                )
            else:
                # Fallback: simple regression (old behavior)
                self.ratings[team] = regressed
        self._current_season = new_season

    def process_game(self, game: GameResult) -> tuple[TeamEloRecord, TeamEloRecord]:
        # Season boundary detection
        season = game.game_date.year
        if self._current_season is not None and season != self._current_season:
            self._season_reset(season)
        elif self._current_season is None:
            self._current_season = season

        home_elo = self._get_elo(game.home_team)
        away_elo = self._get_elo(game.away_team)

        # Expected scores (home gets HFA boost for calculation only)
        home_expected = self._expected_score(home_elo + self.hfa, away_elo)

        # Actual outcomes
        if game.home_score > game.away_score:
            home_actual = 1.0
            home_result, away_result = "W", "L"
        else:
            home_actual = 0.0
            home_result, away_result = "L", "W"

        mov = self._mov_multiplier(game.home_score - game.away_score)

        # Zero-sum ELO update
        home_delta = self.k * mov * (home_actual - home_expected)
        away_delta = -home_delta

        home_elo_after = home_elo + home_delta
        away_elo_after = away_elo + away_delta

        self.ratings[game.home_team] = home_elo_after
        self.ratings[game.away_team] = away_elo_after

        home_rec = TeamEloRecord(
            team_code=game.home_team,
            game_date=game.game_date.isoformat(),
            game_pk=game.game_pk,
            elo_before=round(home_elo, 4),
            elo_after=round(home_elo_after, 4),
            opponent_code=game.away_team,
            result=home_result,
            run_diff=game.home_score - game.away_score,
        )
        away_rec = TeamEloRecord(
            team_code=game.away_team,
            game_date=game.game_date.isoformat(),
            game_pk=game.game_pk,
            elo_before=round(away_elo, 4),
            elo_after=round(away_elo_after, 4),
            opponent_code=game.home_team,
            result=away_result,
            run_diff=game.away_score - game.home_score,
        )

        self.records.extend([home_rec, away_rec])
        return home_rec, away_rec

    def process_season(self, games: list[GameResult]) -> list[TeamEloRecord]:
        for game in games:
            self.process_game(game)
        return self.records


def extract_game_results(pa_rows: list[dict]) -> list[GameResult]:
    """Extract one GameResult per game_pk from raw plate appearance rows.

    Uses the last PA per game (highest pa_id) to read final scores.
    inning_half determines score mapping:
      - 'Top': away team batting → bat_score=away, fld_score=home
      - 'Bot': home team batting → bat_score=home, fld_score=away
    """
    # Group by game_pk, keep only the row with max pa_id
    games: dict[int, dict] = {}
    for row in pa_rows:
        gpk = int(row["game_pk"])
        pa_id = int(row["pa_id"])
        if gpk not in games or pa_id > int(games[gpk]["pa_id"]):
            games[gpk] = row

    results = []
    for row in games.values():
        bat_score = int(row["bat_score"])
        fld_score = int(row["fld_score"])

        if row["inning_half"] == "Top":
            # Away team batting: bat_score=away, fld_score=home
            away_score = bat_score
            home_score = fld_score
        else:
            # Home team batting (Bot): bat_score=home, fld_score=away
            home_score = bat_score
            away_score = fld_score

        # Skip ties (shouldn't happen in MLB, but defensive)
        if home_score == away_score:
            continue

        game_date_str = str(row["game_date"])[:10]
        results.append(
            GameResult(
                game_pk=int(row["game_pk"]),
                game_date=date.fromisoformat(game_date_str),
                home_team=row["home_team"],
                away_team=row["away_team"],
                home_score=home_score,
                away_score=away_score,
            )
        )

    results.sort(key=lambda g: (g.game_date, g.game_pk))
    return results
