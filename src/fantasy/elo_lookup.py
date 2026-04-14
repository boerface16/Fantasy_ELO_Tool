"""Batch ELO lookup from Supabase with in-memory cache.

Fetches talent ELO values for batters and pitchers in bulk,
caches results to avoid repeated queries within a session.
"""

import logging

from src.fantasy._config import get_config

logger = logging.getLogger(__name__)

DEFAULT_BATTER_ELO = {"contact": 1500.0, "power": 1500.0, "discipline": 1500.0, "speed": 1500.0, "clutch": 1500.0}
DEFAULT_PITCHER_ELO = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0, "clutch": 1500.0}

BATTER_TALENTS = ["contact", "power", "discipline", "speed", "clutch"]
PITCHER_TALENTS = ["stuff", "bip_suppression", "command", "clutch"]

# ME-1: OHLC form adjustment config
_FORM_WEIGHT = 0.05       # dampening factor: trend_z * FORM_WEIGHT = form_adjustment
_FORM_DAYS = 7            # look-back window for momentum signal
_FORM_HISTORY = 30        # history rows per dimension for std computation
_FORM_CAP = 0.10          # cap adjustment at ±10%

# ME-4: team ELO constants
TEAM_ELO_MEAN = 1500.0
TEAM_ELO_STD = 50.0
OPPONENT_WIN_WEIGHT = 0.05  # win_prob shift per std deviation of opponent team ELO

_CFG = get_config()
_ENG = _CFG["prediction_engine"]
_SEASON_W: float = _ENG["career_blend_season_weight"]
_CAREER_W: float = _ENG["career_blend_career_weight"]
_RELIABILITY: dict[str, int] = {
    d["name"]: d["reliability_threshold"]
    for d in _CFG.get("batter_dimensions", []) + _CFG.get("pitcher_dimensions", [])
}


def _blend_elo(season_elo: float, career_elo, event_count, talent_type: str) -> float:
    """Blend season and career ELO when event_count is below the reliability threshold.

    For established players (event_count >= threshold), season_elo is returned as-is.
    For call-ups or returning players with thin samples, career_elo anchors the estimate.
    """
    if career_elo is None or event_count is None:
        return float(season_elo)
    if int(event_count) >= _RELIABILITY.get(talent_type, 400):
        return float(season_elo)
    return _SEASON_W * float(season_elo) + _CAREER_W * float(career_elo)


class EloLookup:
    """Batch-loads and caches player talent ELO values."""

    def __init__(self, supabase_client):
        self._client = supabase_client
        self._batter_cache: dict[int, dict[str, float]] = {}
        self._pitcher_cache: dict[int, dict[str, float]] = {}
        self._composite_batter_cache: dict[int, float] = {}
        self._composite_pitcher_cache: dict[int, float] = {}
        self._loaded_ids: set[int] = set()
        self._form_cache: dict[tuple[int, str], float] = {}   # ME-1
        self._form_loaded: set[int] = set()                   # ME-1: which player_ids are loaded
        self._team_elo_cache: dict[str, float] = {}           # ME-4

    def load_batch(self, player_ids: list[int]) -> None:
        """Fetch talent ELO for a batch of player IDs (skips already-cached)."""
        new_ids = [pid for pid in player_ids if pid not in self._loaded_ids]
        if not new_ids:
            return

        self._loaded_ids.update(new_ids)

        # Fetch per-dimension talent ELO
        self._fetch_role(new_ids, "batter", BATTER_TALENTS, self._batter_cache)
        self._fetch_role(new_ids, "pitcher", PITCHER_TALENTS, self._pitcher_cache)

        # Fetch composite ELO as fallback (player_elo table)
        self._fetch_composite(new_ids)

    def _fetch_composite(self, player_ids: list[int]) -> None:
        """Fetch composite batting/pitching ELO from player_elo as fallback."""
        batch_size = 100
        for i in range(0, len(player_ids), batch_size):
            batch = player_ids[i:i + batch_size]
            resp = (
                self._client.table("player_elo")
                .select("player_id, batting_elo, pitching_elo")
                .in_("player_id", batch)
                .execute()
            )
            for row in resp.data or []:
                pid = row["player_id"]
                if row.get("batting_elo"):
                    self._composite_batter_cache[pid] = float(row["batting_elo"])
                if row.get("pitching_elo"):
                    self._composite_pitcher_cache[pid] = float(row["pitching_elo"])

    def _fetch_role(self, player_ids: list[int], role: str, talent_types: list[str],
                    cache: dict[int, dict[str, float]]) -> None:
        """Fetch talent ELO for a specific role in batches."""
        batch_size = 100
        for i in range(0, len(player_ids), batch_size):
            batch = player_ids[i:i + batch_size]
            resp = (
                self._client.table("talent_player_current")
                .select("player_id, talent_type, season_elo, career_elo, event_count")
                .in_("player_id", batch)
                .eq("player_role", role)
                .execute()
            )

            for row in resp.data or []:
                pid = row["player_id"]
                if pid not in cache:
                    cache[pid] = {}
                cache[pid][row["talent_type"]] = _blend_elo(
                    row["season_elo"],
                    row.get("career_elo"),
                    row.get("event_count"),
                    row["talent_type"],
                )

    def get_batter_elo(self, player_id: int) -> dict[str, float]:
        """Get batter talent ELO dict. Falls back to composite player_elo if no talent data."""
        cached = self._batter_cache.get(player_id)
        if cached:
            return {t: cached.get(t, DEFAULT_BATTER_ELO[t]) for t in BATTER_TALENTS}

        composite = self._composite_batter_cache.get(player_id)
        if composite:
            # Use composite as proxy for contact + power; discipline/speed at league mean
            return {
                "contact": composite,
                "power": composite,
                "discipline": DEFAULT_BATTER_ELO["discipline"],
                "speed": DEFAULT_BATTER_ELO["speed"],
            }

        return dict(DEFAULT_BATTER_ELO)

    def get_pitcher_elo(self, player_id: int) -> dict[str, float]:
        """Get pitcher talent ELO dict. Falls back to composite player_elo if no talent data."""
        cached = self._pitcher_cache.get(player_id)
        if cached:
            return {t: cached.get(t, DEFAULT_PITCHER_ELO[t]) for t in PITCHER_TALENTS}

        composite = self._composite_pitcher_cache.get(player_id)
        if composite:
            return {
                "stuff": composite,
                "bip_suppression": composite,
                "command": DEFAULT_PITCHER_ELO["command"],
                "clutch": DEFAULT_PITCHER_ELO["clutch"],
            }

        return dict(DEFAULT_PITCHER_ELO)

    # ME-1: Recent form (OHLC trend) -------------------------------------------

    def get_recent_form_adjustment(self, player_id: int, dimension: str) -> float:
        """Return ELO multiplier in [0.90, 1.10] based on 7-day OHLC momentum.

        Queries talent_daily_ohlc once per player (all dimensions batched), then
        caches. Returns 1.0 (no adjustment) when player_id is missing or data is thin.
        """
        if not player_id:
            return 1.0
        if player_id not in self._form_loaded:
            self._load_player_form(player_id)
        return self._form_cache.get((player_id, dimension), 1.0)

    def _load_player_form(self, player_id: int) -> None:
        """Batch-load OHLC rows for all dimensions of one player, compute multipliers."""
        self._form_loaded.add(player_id)

        resp = (
            self._client.table("talent_daily_ohlc")
            .select("talent_type, game_date, open_elo, close_elo")
            .eq("player_id", player_id)
            .eq("elo_type", "SEASON")
            .order("game_date", desc=True)
            .limit(_FORM_HISTORY * 10)  # up to 30 rows × ~10 dimensions
            .execute()
        )

        # Group by dimension
        by_dim: dict[str, list] = {}
        for row in resp.data or []:
            by_dim.setdefault(row["talent_type"], []).append(row)

        for dim, rows in by_dim.items():
            rows_asc = sorted(rows, key=lambda r: r["game_date"])
            last_30 = rows_asc[-_FORM_HISTORY:]
            if len(last_30) < _FORM_DAYS:
                self._form_cache[(player_id, dim)] = 1.0
                continue

            last_7 = last_30[-_FORM_DAYS:]
            trend = last_7[-1]["close_elo"] - last_7[0]["open_elo"]

            closes = [r["close_elo"] for r in last_30]
            mean_c = sum(closes) / len(closes)
            std_c = (sum((x - mean_c) ** 2 for x in closes) / len(closes)) ** 0.5

            trend_z = trend / std_c if std_c > 0 else 0.0
            form_adj = max(-_FORM_CAP, min(_FORM_CAP, trend_z * _FORM_WEIGHT))
            self._form_cache[(player_id, dim)] = 1.0 + form_adj

    # ME-4: Team ELO lookup -----------------------------------------------------

    def load_teams(self, team_codes: list[str]) -> None:
        """Fetch most-recent ELO (elo_after) for each team code and cache it."""
        new_codes = [c for c in team_codes if c not in self._team_elo_cache]
        if not new_codes:
            return
        for code in new_codes:
            resp = (
                self._client.table("team_elo")
                .select("elo_after")
                .eq("team_code", code)
                .order("game_date", desc=True)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            self._team_elo_cache[code] = float(rows[0]["elo_after"]) if rows else TEAM_ELO_MEAN

    def get_team_elo(self, team_code: str) -> float:
        """Return cached team ELO (most recent game elo_after), defaulting to league mean."""
        return self._team_elo_cache.get(team_code, TEAM_ELO_MEAN)
