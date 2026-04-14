"""Shared config loader — reads multi_elo_config.yaml once and caches it."""

import os
import yaml
from functools import lru_cache


@lru_cache(maxsize=1)
def get_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "multi_elo_config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)
