"""Batch ELO lookup from Supabase with in-memory cache.

Fetches talent ELO values for batters and pitchers in bulk,
caches results to avoid repeated queries within a session.
"""

import logging

logger = logging.getLogger(__name__)

DEFAULT_BATTER_ELO = {"contact": 1500.0, "power": 1500.0, "discipline": 1500.0}
DEFAULT_PITCHER_ELO = {"stuff": 1500.0, "bip_suppression": 1500.0, "command": 1500.0}

BATTER_TALENTS = ["contact", "power", "discipline"]
PITCHER_TALENTS = ["stuff", "bip_suppression", "command"]


class EloLookup:
    """Batch-loads and caches player talent ELO values."""

    def __init__(self, supabase_client):
        self._client = supabase_client
        self._batter_cache: dict[int, dict[str, float]] = {}
        self._pitcher_cache: dict[int, dict[str, float]] = {}
        self._loaded_ids: set[int] = set()

    def load_batch(self, player_ids: list[int]) -> None:
        """Fetch talent ELO for a batch of player IDs (skips already-cached)."""
        new_ids = [pid for pid in player_ids if pid not in self._loaded_ids]
        if not new_ids:
            return

        self._loaded_ids.update(new_ids)

        # Fetch batter talents
        self._fetch_role(new_ids, "batter", BATTER_TALENTS, self._batter_cache)
        # Fetch pitcher talents
        self._fetch_role(new_ids, "pitcher", PITCHER_TALENTS, self._pitcher_cache)

    def _fetch_role(self, player_ids: list[int], role: str, talent_types: list[str],
                    cache: dict[int, dict[str, float]]) -> None:
        """Fetch talent ELO for a specific role in batches."""
        batch_size = 100
        for i in range(0, len(player_ids), batch_size):
            batch = player_ids[i:i + batch_size]
            resp = (
                self._client.table("talent_player_current")
                .select("player_id, talent_type, season_elo")
                .in_("player_id", batch)
                .eq("player_role", role)
                .execute()
            )

            for row in resp.data or []:
                pid = row["player_id"]
                if pid not in cache:
                    cache[pid] = {}
                cache[pid][row["talent_type"]] = row["season_elo"]

    def get_batter_elo(self, player_id: int) -> dict[str, float]:
        """Get batter talent ELO dict. Returns defaults if not found."""
        cached = self._batter_cache.get(player_id)
        if not cached:
            return dict(DEFAULT_BATTER_ELO)
        return {
            t: cached.get(t, DEFAULT_BATTER_ELO[t])
            for t in BATTER_TALENTS
        }

    def get_pitcher_elo(self, player_id: int) -> dict[str, float]:
        """Get pitcher talent ELO dict. Returns defaults if not found."""
        cached = self._pitcher_cache.get(player_id)
        if not cached:
            return dict(DEFAULT_PITCHER_ELO)
        return {
            t: cached.get(t, DEFAULT_PITCHER_ELO[t])
            for t in PITCHER_TALENTS
        }
