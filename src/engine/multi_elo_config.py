"""Multi-ELO Config Loader (9D Talent System)."""
from pathlib import Path
import yaml


class MultiEloConfig:
    """YAML-based Multi-ELO configuration."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "multi_elo_config.yaml"

    def __init__(self, config_path: Path | str | None = None):
        path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        with open(path, encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
        self._build_indices()

    def _build_indices(self) -> None:
        self._batter_dim_map = {d["name"]: d for d in self._config["batter_dimensions"]}
        self._pitcher_dim_map = {d["name"]: d for d in self._config["pitcher_dimensions"]}

    @property
    def version(self) -> str:
        return self._config["version"]

    @property
    def batter_dimensions(self) -> list[dict]:
        return self._config["batter_dimensions"]

    @property
    def pitcher_dimensions(self) -> list[dict]:
        return self._config["pitcher_dimensions"]

    def get_event_weights(self, event_type: str) -> dict[str, float]:
        weights = self._config["event_weights"].get(event_type, {})
        result = {"contact": 0.0, "power": 0.0, "discipline": 0.0, "speed": 0.0, "clutch_base": 0.0}
        result.update(weights)
        return result

    def get_pitcher_event_weights(self, event_type: str) -> dict[str, float]:
        weights = self._config.get("pitcher_event_weights", {}).get(event_type, {})
        result = {"stuff": 0.0, "bip_suppression": 0.0, "command": 0.0, "clutch_base": 0.0}
        result.update(weights)
        return result

    def get_batter_k_factor(self, dimension: str) -> float:
        return self._batter_dim_map.get(dimension, {}).get("k_factor", 12.0)

    def get_pitcher_k_factor(self, dimension: str) -> float:
        return self._pitcher_dim_map.get(dimension, {}).get("k_factor", 12.0)

    def get_batter_scale(self, dimension: str) -> float:
        return self._batter_dim_map.get(dimension, {}).get("scale", 5.0)

    def get_pitcher_scale(self, dimension: str) -> float:
        return self._pitcher_dim_map.get(dimension, {}).get("scale", 5.0)

    def get_reliability_threshold(self, dimension: str, is_pitcher: bool = False) -> int:
        dim_map = self._pitcher_dim_map if is_pitcher else self._batter_dim_map
        return dim_map.get(dimension, {}).get("reliability_threshold", 400)

    def get_expected_divisor(self, dimension: str, is_pitcher: bool = False) -> float:
        dim_map = self._pitcher_dim_map if is_pitcher else self._batter_dim_map
        default = self._config.get("constants", {}).get("default_expected_divisor", 400.0)
        return dim_map.get(dimension, {}).get("expected_divisor", default)

    def get_batter_composite_weights(self) -> dict[str, float]:
        return self._config["composite_weights"]["batter"]["default"].copy()

    def get_pitcher_composite_weights(self, role: str = "starter") -> dict[str, float]:
        pw = self._config["composite_weights"]["pitcher"]
        return pw.get(role, pw["starter"]).copy()

    @property
    def leverage_threshold(self) -> float:
        return self._config["clutch_config"]["leverage_threshold"]

    @property
    def max_clutch_multiplier(self) -> float:
        return self._config["clutch_config"]["max_multiplier"]
