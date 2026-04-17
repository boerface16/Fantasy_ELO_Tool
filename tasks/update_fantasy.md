# Opponent-Context Fantasy Projection Improvements

## Context

The fantasy projection engine already uses opponents in several ways (opponent pitcher ELO, home/away flag, historical vs-team PAs, team ELO for win probability, pitcher SB-allow rate). However, three meaningful opponent signals are available but unused in projections:

1. **Opponent pitcher recent form** — the batter's own OHLC form is adjusted (ME-1), but the opposing pitcher's hot/cold streak is not reflected
2. **Park factors** — `data/mlb_park_factors.csv` and `src/engine/park_factor.py` exist but are only used during ELO training, not projection
3. **Opponent team offensive strength for SP** — `predict_plate_appearance(AVG_BATTER_ELO, pitcher_elo)` always uses league-average batters regardless of who the SP actually faces

## Tasks

- [ ] Step 1 — Config additions
- [ ] Step 2 — ME-5: Opponent pitcher form
- [ ] Step 3 — PF-1: Park factor integration (matchup_predictor.py + weekly_projection.py)
- [ ] Step 4 — ME-6: Opponent team offensive strength for SP
- [ ] Step 5 — Tests

---

## Critical Files

- `config/multi_elo_config.yaml` — `prediction_engine` section ends at line 309; add new feature configs here
- `src/fantasy/matchup_predictor.py` — `predict_plate_appearance()` at line 124; add `park_factor` param
- `src/fantasy/weekly_projection.py` — batter loop at line 287, SP loop at line 387
- `src/engine/park_factor.py` — `ParkFactor.get_park_factor(home_team) → float` (already loads CSV; returns 1.0 for unknowns)
- `src/fantasy/elo_lookup.py` — `get_recent_form_adjustment(player_id, dim) → float` already works for any player_id
- `tests/test_matchup_predictor_py.py` and `tests/test_weekly_projection.py`

---

## Step 1 — Config (`config/multi_elo_config.yaml`)

Append to `prediction_engine` section (after line 308 `speed_3b_scale`):

```yaml
  me5_opponent_pitcher_form:
    enabled: true

  pf1_park_factor:
    enabled: true
    logit_scale: 1.0   # multiplier on (park_factor - 1.0) before logit shift

  me6_opponent_team_offense:
    enabled: true
    team_elo_mean: 1500.0
    team_elo_std: 50.0
    dimension_scale: 0.5   # fraction of team z-score applied per batter dimension
```

---

## Step 2 — ME-5: Opponent Pitcher Form (`weekly_projection.py`)

**At module top**, after `_ENG = get_config()["prediction_engine"]`, add:

```python
_FEATURE_FLAGS = {
    "me5_opponent_pitcher_form": _ENG.get("me5_opponent_pitcher_form", {}).get("enabled", False),
    "pf1_park_factor":           _ENG.get("pf1_park_factor", {}).get("enabled", False),
    "me6_opponent_team_offense": _ENG.get("me6_opponent_team_offense", {}).get("enabled", False),
}
```

**In the batter loop**, after fetching `pitcher_elo` (after line ~301, before `batter_elo = ...`):

```python
# ME-5: apply recent-form adjustment to opponent pitcher dimensions
if _FEATURE_FLAGS["me5_opponent_pitcher_form"] and supabase and m.opponent_pitcher_id:
    for dim in list(pitcher_elo):
        pitcher_elo[dim] *= elo_lookup.get_recent_form_adjustment(m.opponent_pitcher_id, dim)
```

`get_recent_form_adjustment` already guards against missing IDs (returns 1.0). No changes to `elo_lookup.py` needed.

---

## Step 3 — PF-1: Park Factor Integration

### Part A — `matchup_predictor.py`

Add to module-level config loading (after `_XBH` block):

```python
_PF_CFG: dict = _PRED_CFG.get("pf1_park_factor", {})
_PF_LOGIT_SCALE: float = _PF_CFG.get("logit_scale", 1.0)
```

Add `park_factor: float = 1.0` to `predict_plate_appearance()` signature (default=1.0 protects all existing callers).

After the ME-3 home-field logit shift (after line ~175), add:

```python
# PF-1: park factor logit shift to Stage 2 hit probability
# Hitter-friendly park (>1.0) → more hits; pitcher-friendly (<1.0) → fewer
pf_logit_shift = (park_factor - 1.0) * _PF_LOGIT_SCALE
if pf_logit_shift != 0.0:
    logit_pf = math.log(p_hit_given_bip / (1.0 - p_hit_given_bip)) + pf_logit_shift
    p_hit_given_bip = 1.0 / (1.0 + math.exp(-logit_pf))
```

### Part B — `weekly_projection.py`

Add import and module-level instantiation:

```python
from src.engine.park_factor import ParkFactor as _ParkFactorClass

_park_factor_lookup: _ParkFactorClass | None = None
if _FEATURE_FLAGS["pf1_park_factor"]:
    try:
        _park_factor_lookup = _ParkFactorClass()
    except Exception as _pf_err:
        logger.warning(f"PF-1 disabled — could not load park factors: {_pf_err}")
```

Add helper function near `compute_composite_elo`:

```python
def _get_park_factor(m) -> float:
    """Return park factor for this matchup's venue. 1.0 if PF-1 disabled or unknown."""
    if _park_factor_lookup is None:
        return 1.0
    home_team = m.player_team if m.is_home else m.opponent_team
    return _park_factor_lookup.get_park_factor(home_team)
```

Update **batter loop** `predict_plate_appearance` call (line ~317):
```python
pred = predict_plate_appearance(
    batter_elo, pitcher_elo,
    clutch_elo=clutch_elo,
    is_home=m.is_home,
    speed_elo=speed_elo,
    park_factor=_get_park_factor(m),   # PF-1
)
```

Update **SP loop** `predict_plate_appearance` call (line ~395):
```python
pitcher_pred = predict_plate_appearance(
    opp_batter_elo, pitcher_own_elo,   # ME-6 supplies opp_batter_elo
    park_factor=_get_park_factor(m),   # PF-1: Coors → more hits against SP
)
```

RP loop leaves default `park_factor=1.0` — RP projections span multiple venues, neutral is appropriate.

---

## Step 4 — ME-6: Opponent Team Offensive Strength for SP (`weekly_projection.py`)

Update import from `matchup_predictor`:
```python
from src.fantasy.matchup_predictor import predict_plate_appearance, LEAGUE_AVG_WOBA, MLB_ELO_DISTRIBUTION
```

Add helper function:

```python
def _build_opponent_batter_elo(opponent_team: str, elo_lookup: EloLookup) -> dict[str, float]:
    """Map opponent team ELO → per-dimension batter ELO dict for SP projections (ME-6).

    Team z-score scales each AVG_BATTER_ELO dimension by dimension_scale * that dim's std.
    A stronger team (higher team ELO) yields higher effective batter ELO against the SP.
    Only used for SP starts; RP projections use AVG_BATTER_ELO (spans many opponents).
    """
    cfg = _ENG.get("me6_opponent_team_offense", {})
    team_mean: float = cfg.get("team_elo_mean", TEAM_ELO_MEAN)
    team_std: float = cfg.get("team_elo_std", TEAM_ELO_STD)
    dim_scale: float = cfg.get("dimension_scale", 0.5)

    team_elo = elo_lookup.get_team_elo(opponent_team)
    team_z = (team_elo - team_mean) / team_std if team_std > 0 else 0.0

    result: dict[str, float] = {}
    for dim, base_elo in AVG_BATTER_ELO.items():
        dist_key = f"BATTER_{dim.upper()}"
        dim_std = MLB_ELO_DISTRIBUTION.get(dist_key, {}).get("std", 50.0)
        result[dim] = base_elo + team_z * dim_scale * dim_std
    return result
```

In **SP loop**, replace `AVG_BATTER_ELO` (line ~395):

```python
# ME-6: use opponent team offensive strength rather than league-average batter ELO
if _FEATURE_FLAGS["me6_opponent_team_offense"]:
    opp_batter_elo = _build_opponent_batter_elo(m.opponent_team, elo_lookup)
else:
    opp_batter_elo = AVG_BATTER_ELO

pitcher_pred = predict_plate_appearance(
    opp_batter_elo, pitcher_own_elo,
    park_factor=_get_park_factor(m),
)
```

`load_teams()` is called at line ~270 before the SP loop, so team ELO cache is pre-populated.

---

## Step 5 — Tests

Add to `tests/test_matchup_predictor_py.py`:

```python
def test_park_factor_neutral_no_change(avg_batter, avg_pitcher):
    base = predict_plate_appearance(avg_batter, avg_pitcher)
    pf1  = predict_plate_appearance(avg_batter, avg_pitcher, park_factor=1.0)
    assert base["expected_woba"] == pytest.approx(pf1["expected_woba"], abs=1e-9)

def test_high_park_factor_raises_woba(avg_batter, avg_pitcher):
    base  = predict_plate_appearance(avg_batter, avg_pitcher)
    coors = predict_plate_appearance(avg_batter, avg_pitcher, park_factor=1.13)
    assert coors["expected_woba"] > base["expected_woba"]

def test_low_park_factor_lowers_woba(avg_batter, avg_pitcher):
    base  = predict_plate_appearance(avg_batter, avg_pitcher)
    petco = predict_plate_appearance(avg_batter, avg_pitcher, park_factor=0.87)
    assert petco["expected_woba"] < base["expected_woba"]

def test_park_factor_probabilities_sum_to_one(avg_batter, avg_pitcher):
    pred = predict_plate_appearance(avg_batter, avg_pitcher, park_factor=1.13)
    assert abs(sum(pred["probabilities"].values()) - 1.0) < 1e-6
```

---

## Verification

- **ME-5**: Mock pitcher form at 0.90 for all dims → batter wOBA against them should rise ~2-3 points
- **PF-1**: Coors (1.13) → wOBA rises vs neutral; Petco (0.87) → wOBA drops; probs sum to 1.0
- **ME-6**: Team ELO 1600 (z=+2) → SP wOBA-against exceeds league average; Team ELO 1400 (z=−2) → below average
- Run `tests/test_matchup_predictor_py.py` and `tests/test_weekly_projection.py` with no errors

## Implementation Order

1. Config additions
2. ME-5 (zero-risk, no new parameters)
3. PF-1 (touches `matchup_predictor.py` signature; default=1.0 protects all other callers)
4. ME-6 (builds on PF-1's updated call site)
