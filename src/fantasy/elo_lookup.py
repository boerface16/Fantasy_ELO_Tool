"""Batch ELO lookup from Supabase with in-memory cache.

Fetches talent ELO values for batters and pitchers in bulk,
caches results to avoid repeated queries within a session.
"""

import logging
import os
import yaml

logger = logging.getLogger(__name__)

DEFAULT_BATTER_ELO = {"contact": 1500.0, "power": 1500.0, "discipline": 1500.0, "speed": 1500.0}
DEFAULT_PITCHER_ELO = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0, "clutch": 1500.0}

BATTER_TALENTS = ["contact", "power", "discipline", "speed"]
PITCHER_TALENTS = ["stuff", "bip_suppression", "command", "clutch"]

# Load blend config from multi_elo_config.yaml (QW-3)
_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "multi_elo_config.yaml")
with open(_CFG_PATH) as _f:
    _CFG = yaml.safe_load(_f)

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
