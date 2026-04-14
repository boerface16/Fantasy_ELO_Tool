## Completed 4/10/26


# Prediction System Improvement Plan

Generated: 2026-04-09

This plan covers the gap between available data (9D talent ELO, OHLC trend, team ELO, career/season split) and what is actually used, plus structural modeling weaknesses in the 3-stage decision tree.

---

## Quick Wins

These are low-complexity changes with high confidence of improving accuracy. Each can be done in isolation in a single session.

---

### QW-1: Incorporate pitcher clutch ELO into win/loss probability

**What to change:**
In `weekly_projection.py` lines 367–371, `win_prob` is computed from a scalar `woba_diff` against a fixed baseline. The pitcher's `clutch` ELO dimension is fetched (it is in `pitcher_own_elo`) but is never used.

Add a clutch adjustment to the win probability formula:
```
z_clutch = (pitcher_clutch_elo - CLUTCH_MEAN) / CLUTCH_STD
win_prob += z_clutch * CLUTCH_WIN_WEIGHT   # e.g. 0.02
```
Cap remains the same (`max(0.10, min(0.55, ...))`).

**Why it helps:**
Clutch ELO tracks high-leverage performance — exactly the conditions that determine whether a starter holds a lead through the 6th inning. A pitcher with 1700 clutch ELO earns wins at a meaningfully higher rate than one at 1300, independent of raw stuff/command.

**Files:** `src/fantasy/weekly_projection.py` (lines 367–371); add clutch distribution constants to `matchup_predictor.py` MLB_ELO_DISTRIBUTION dict.

**Complexity:** Small.

---

### QW-2: Fix pitcher power exclusion from Stage 3 — use pitcher stuff vs batter power diff

**What to change:**
In `matchup_predictor.py` line 121–122, `p_xbh_given_hit` is computed from `z_power` alone (batter standalone). This ignores pitcher influence on extra-base rate. Replace with a z-score diff:

```python
z_stuff_power = z_stuff - z_power   # pitcher suppresses XBH
p_xbh_given_hit = zscore_to_probability(
    -z_stuff_power, ZSCORE_DIVISOR["stage3"], MLB_LEAGUE_AVERAGES["xbh_rate_on_hit"]
)
```

**Why it helps:**
A fly-ball specialist pitcher at 1650 stuff dramatically suppresses HR rates regardless of batter power. The current model predicts the same HR rate against Max Fried as against a mop-up reliever for the same batter. The empirical HR rate against elite stuff pitchers is ~25–30% lower than against below-average pitchers for the same batter profile.

**Files:** `src/fantasy/matchup_predictor.py` (lines 121–122, and `z_diffs` return dict at line 148).

**Complexity:** Small.

---

### QW-3: Career/season ELO blending in `elo_lookup.py`

**What to change:**
The `talent_player_current` table has both `season_elo` and `career_elo` columns. The current ELO lookup almost certainly uses `season_elo` only (verify in `elo_lookup.py`). Blend them using the `season_reset` weights already defined in `multi_elo_config.yaml`:

```
blended = projection_weight * season_elo + prior_weight * career_elo
# = 0.67 * season_elo + 0.33 * career_elo
```

Apply only when `event_count < reliability_threshold` for that dimension (from config). For players with 400+ events, `season_elo` dominates; for call-ups or injured returners, `career_elo` prevents cold-start regression to 1500.

**Why it helps:**
A batter with 50 season PAs and a 1420 contact ELO is being treated as worse than a true-talent 1500 replacement. Their career ELO of 1580 (established over 2000 PAs) is a far better estimate. The `season_reset` weights in config already encode this philosophy — it just isn't applied at lookup time.

**Files:** `src/fantasy/elo_lookup.py` (wherever `season_elo` is selected from DB); `config/multi_elo_config.yaml` (values already present).

**Complexity:** Small.

---

### QW-4: Replace fixed `innings=6.0` for SP with per-pitcher Fangraphs IP/GS

**What to change:**
In `weekly_projection.py` line 373, every SP start is projected at `innings=6.0` regardless of who the pitcher is. The `fg_by_name` dict is already loaded and available in scope. Add:

```python
fg_sp = fg_by_name.get(name.lower(), {})
gs = float(fg_sp.get("GS") or 1)
season_ip_sp = float(fg_sp.get("IP") or 0)
avg_ip_per_start = max(4.0, min(7.5, season_ip_sp / gs)) if gs > 0 else 6.0
```

Then pass `innings=avg_ip_per_start` to `estimate_pitcher_points`.

**Why it helps:**
A five-inning pitcher (e.g., a young SP capped at 85 pitches) projected at 6 innings earns +3 phantom IP points per start — a persistent bias of ~3 pts/start. `IP` and `GS` are already in the Fangraphs payload, so this is zero additional API cost.

**Files:** `src/fantasy/weekly_projection.py` (lines 363–386).

**Complexity:** Small.

---

### QW-5: Fix `AVG_BATTER_ELO` missing `clutch` key

**What to change:**
In `weekly_projection.py` line 39, `AVG_BATTER_ELO` is defined as:
```python
AVG_BATTER_ELO = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}
```
This is used in pitcher projections (lines 366, 406). The `predict_plate_appearance` function receives this dict and calls `batter["contact"]`, `batter["power"]`, `batter["discipline"]` — so the missing `speed` and `clutch` keys don't cause a crash, but if any future use expects a full batter dict, it will silently default to 0. Add:
```python
AVG_BATTER_ELO = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3, "speed": 1500.0, "clutch": 1500.0}
```

Also: the values 1504.5, 1468.6, 1700.3 are already hard-coded in `matchup_predictor.py`'s `MLB_ELO_DISTRIBUTION` means. They should come from config, not be duplicated. Add a `avg_batter_elo` block to `multi_elo_config.yaml` and load it in both files.

**Why it helps:**
Eliminates silent mismatch between two places that hardcode the same distribution means. Any future recalibration only needs to change one place.

**Files:** `src/fantasy/weekly_projection.py` line 39; `config/multi_elo_config.yaml`.

**Complexity:** Small.

---

## Medium Enhancements

These require 1–2 sessions and touch multiple files, but don't restructure the core pipeline.

---

### ME-1: Incorporate recent form (OHLC trend) as a short-term ELO adjustment

**What to change:**
The `talent_daily_ohlc` table tracks per-dimension ELO candlesticks. A simple 7-day momentum signal can be computed per player per dimension:

```
trend_z = (close_elo_last7 - open_elo_last7) / rolling_std_last30
form_adjustment = trend_z * FORM_WEIGHT   # e.g. 0.05 dampening factor
adjusted_elo = season_elo * (1 + form_adjustment)
```

Practically: add a method `get_recent_form_adjustment(player_id, dimension, days=7)` in `elo_lookup.py` that queries `talent_daily_ohlc` for the last N rows and returns a scalar multiplier. Apply in `weekly_projection.py` before calling `predict_plate_appearance`.

Cap the adjustment at ±10% of the ELO value to prevent hot-streak overreaction.

**Why it helps:**
A batter who has gained +80 contact ELO over the last 7 days is in demonstrably better recent form than their season average suggests. Conversely, an injured-returning pitcher whose stuff ELO has dropped -120 over 10 days should not be projected at their season average. Weekly fantasy hinges on hot/cold streaks — this is the most direct signal available.

**Why capped:** ELO reverts to mean; a +80 swing in 7 days is partly signal, partly variance. Capping at ±10% respects the signal without chasing noise.

**Files:** `src/fantasy/elo_lookup.py` (new method); `src/fantasy/weekly_projection.py` (apply adjustment before prediction).

**Complexity:** Medium.

---

### ME-2: Integrate batter clutch ELO into high-leverage PA weighting

**What to change:**
The `plate_appearances` table has `on_1b`, `on_2b`, `on_3b`, and `outs_when_up`. These were used by the ELO engine to compute clutch ratings. The prediction model ignores them entirely. Add a leverage-weighted expected points calculation:

1. Estimate the fraction of a batter's PAs that are high-leverage (use a fixed MLB average: ~20% of PAs have LI > 1.5, based on published research).
2. For those PAs, scale the outcome probabilities by the batter's clutch ELO:
   ```
   z_clutch = (batter_clutch_elo - CLUTCH_MEAN) / CLUTCH_STD
   clutch_multiplier = 1.0 + z_clutch * CLUTCH_PA_SCALE  # e.g. 0.08
   high_lev_probs = {k: v * clutch_multiplier for k,v in probs.items() if k != 'K'}
   ```
3. Blend: `final_probs = 0.80 * base_probs + 0.20 * high_lev_probs`

**Why it helps:**
Clutch ELO is accumulated precisely from high-leverage PAs (leverage_threshold=2.0 in config). A batter with 1650 clutch consistently outperforms their baseline in RBI/run-scoring situations. These situations are disproportionately valuable in fantasy because they convert TBs into R+RBI points. Ignoring clutch means projecting Pete Alonso identically to a similarly-powered but low-clutch batter.

**Files:** `src/fantasy/matchup_predictor.py` (new stage or post-process); `src/fantasy/weekly_projection.py` (pass `clutch_elo` to prediction); `src/engine/multi_elo_types.py` (BATTER_DIM_NAMES already has `clutch` at index 4).

**Complexity:** Medium.

---

### ME-3: Home/away split adjustment using `is_home` flag

**What to change:**
`GameMatchup` already stores `is_home` (line 65, `weekly_projection.py`). The prediction ignores it. Add a home/away adjustment to the expected wOBA:

- Source: `team_elo` table — each game row has the team's `elo_before` and `opponent_code`. MLB-wide home advantage is approximately +0.010 wOBA (well-documented).
- Implementation: add a `home_woba_boost = 0.010 if is_home else 0.0` applied as a logit shift to the Stage 2 hit probability before computing final probs.
- Optionally use the `team_elo` table to get a ballpark-specific adjustment: teams that consistently have high `elo_after - elo_before` at home can inform a per-stadium factor. Start with a flat MLB average.

**Why it helps:**
Every model that ignores home/away context is missing a statistically verified ~3% hit probability boost. For a batter with 4 home games in a week vs 4 away games, this is a meaningful spread.

**Files:** `src/fantasy/weekly_projection.py` (pass `is_home` into prediction call); `src/fantasy/matchup_predictor.py` (add `home_boost` parameter to `predict_plate_appearance`).

**Complexity:** Medium.

---

### ME-4: Opponent team strength modifier for SP win probability

**What to change:**
In `weekly_projection.py` lines 367–371, `win_prob` is computed purely from the pitcher's own quality against a league-average lineup. The `team_elo` table has current team ELO values per game.

Add an opponent adjustment:
```python
opp_team_elo = team_elo_lookup.get(m.opponent_team)  # from team_elo table
opp_z = (opp_team_elo - TEAM_ELO_MEAN) / TEAM_ELO_STD
win_prob -= opp_z * OPPONENT_WIN_WEIGHT  # strong team reduces win prob
```

The `team_elo` table (`team_code, game_date, elo_before, elo_after`) is already populated by the pipeline.

**Why it helps:**
Projecting the same win probability for a start against the Dodgers vs the A's is a structural error. A pitcher with 0.35 baseline win probability faces ~0.28 against top-5 offenses and ~0.42 against bottom-5. Wins are worth 2 ESPN points and are the highest-variance batter-dependent stat in pitcher scoring.

**Files:** `src/fantasy/weekly_projection.py` (fetch team ELO, apply adjustment); `src/fantasy/elo_lookup.py` (add `get_team_elo(team_code)` method querying `team_elo`).

**Complexity:** Medium.

---

### ME-5: R and RBI estimation improvement — use baserunner context

**What to change:**
In `fantasy_calculator.py` lines 63–64:
```python
e_runs = e_tb * 0.40
e_rbi = e_tb * 0.45
```
These are flat multipliers with no batter-context. Two improvements:

1. **Speed-adjusted runs:** Faster batters score runs at a higher rate independent of TBs. Add `runs_speed_adj = speed_z * 0.015` per PA to `e_runs`.
2. **Lineup position context:** The ESPN roster doesn't surface batting order, but team-level run-scoring rate per game (from `team_elo` or a static lookup) can scale the R/RBI multipliers. Teams scoring 5.2 R/G produce R/RBI at ~12% above the multipliers that were likely calibrated on ~4.5 R/G teams.

These constants (0.40, 0.45) are hard-coded in `fantasy_calculator.py` with no config backing — they should be moved to `espn_scoring.yaml` as calibration parameters.

**Why it helps:**
R and RBI together account for 2 points per extra base hit (TB=1, R=1, RBI=1 for a typical XBH). Getting the multipliers wrong by 10% propagates through the entire batter projection. Speed adjustment directly ties into the existing speed ELO that is already computed but underused.

**Files:** `src/fantasy/fantasy_calculator.py` (lines 63–64, 69–70); `config/espn_scoring.yaml` (add `r_per_tb` and `rbi_per_tb` calibration keys).

**Complexity:** Medium.

---

## Larger Reworks

These require significant design and testing effort. Prioritize only after quick wins and medium enhancements are validated.

---

### LR-1: Empirically calibrate the ZSCORE_DIVISOR constants

**What to change:**
The four `ZSCORE_DIVISOR` values in `matchup_predictor.py` (3.5, 3.5, 5.0, 5.0) determine how steeply ELO differences shift outcome probabilities. These appear to have been set by hand or inherited from a prior version, not fit to empirical data.

Run a calibration against the `plate_appearances` table:
1. For each PA, look up the batter and pitcher ELOs at the time of the PA (or as of season start — requires joining `talent_daily_ohlc` or `talent_player_current` filtered by `game_date`).
2. Compute predicted probabilities using the current divisors.
3. Minimize log-loss (or Brier score) against observed `result_type` outcomes using grid search or scipy.optimize on the four divisors.

The expected result: Stage 1 BB divisor is likely too permissive (currently 3.5 — every 1 std difference shifts BB rate by ~40%), and Stage 3 power divisor may be underfit (5.0).

**Why it helps:**
This is the single highest-leverage improvement in the entire pipeline. The divisors are the primary calibration levers for prediction accuracy. Miscalibrated divisors produce systematically biased probabilities for elite vs replacement-level players — exactly where fantasy roster decisions are made.

**Files:** `src/fantasy/matchup_predictor.py` (`ZSCORE_DIVISOR` dict, lines 33–37); new calibration notebook in `notebooks/`; potentially move divisors to `multi_elo_config.yaml` so they're not hardcoded.

**Complexity:** Large.

---

### LR-2: Replace fixed 2B/3B/HR split ratios with pitcher-batter interaction model

**What to change:**
In `matchup_predictor.py` lines 126–128:
```python
p_2b = p_xbh * MLB_LEAGUE_AVERAGES["2b_ratio"]   # 0.5522
p_3b = p_xbh * MLB_LEAGUE_AVERAGES["3b_ratio"]   # 0.0448
p_hr = p_xbh * MLB_LEAGUE_AVERAGES["hr_ratio"]   # 0.4030
```
These are fixed MLB averages applied to every batter equally. The 2B/3B/HR split is strongly player-dependent (speed drives 3B rate; pure power drives HR rate) and pitcher-dependent (fly-ball pitchers suppress 3B, allow more HR; ground-ball pitchers do the opposite).

Proposed approach:
1. Add a `hr_ratio_adjustment` driven by batter power z-score and pitcher stuff z-score:
   ```
   hr_ratio = MLB_AVG_HR_RATIO + z_power * POWER_HR_SCALE - z_stuff * STUFF_HR_SCALE
   ```
2. Add a `3b_ratio_adjustment` driven by batter speed ELO:
   ```
   3b_ratio = MLB_AVG_3B_RATIO + z_speed * SPEED_3B_SCALE
   ```
3. Renormalize ratios to sum to 1.0.

**Why it helps:**
HR vs 2B is a +2 vs +1 ESPN scoring difference per event. A batter with 1650 power hitting a XBH deserves HR probability 30–40% above MLB average; a contact-only hitter at 1350 power deserves well below. The current model assigns them identical HR rates after the stage 3 gate, wasting the power signal already computed. Speed ELO is currently entirely unused in the probability tree — batter speed contributes to triples prediction here at essentially zero cost.

**Files:** `src/fantasy/matchup_predictor.py` (lines 126–128); `config/multi_elo_config.yaml` (add `xbh_split_scales` config block).

**Complexity:** Large.

---

### LR-3: Introduced a 4th stage for HBP/IBB as separate probability paths

**What to change:**
Currently HBP and IBB are lumped into the BB bucket in `_RT_TO_PROB` (line 52–53 of `weekly_projection.py`). In the ELO system they are distinct events with different weights. In the prediction model, there is no HBP probability — it silently absorbs into BB rate.

Add HBP as a separate outcome with its own base rate:
- MLB HBP rate ≈ 1.1% of PAs. This is driven by batter crowding the plate (a contact/discipline trait) and pitcher wildness (command trait, but different from walk wildness).
- Split the current BB-or-HBP probability from Stage 1 into BB (discipline vs command) and HBP (weaker discipline signal, stronger command signal).

**Why it helps:**
HBP scores the same ESPN points as BB (1 pt for BB/HBP in ESPN). More importantly, IBB (intentional walk) is currently boosting walk probability for power hitters in ways that artificially inflate their BB projections — IBB has discipline_weight=0.6 in the ELO engine but is fundamentally a pitcher decision. Separating the paths improves probability calibration for high-power batters.

**Files:** `src/fantasy/matchup_predictor.py` (Stage 1 softmax expansion); `src/fantasy/fantasy_calculator.py` (add `HBP` to probs scoring); `config/multi_elo_config.yaml` (add HBP base rate).

**Complexity:** Large.

---

### LR-4: Build a backtesting harness to evaluate projection accuracy

**What to change:**
There is currently no systematic way to measure whether predictions are accurate. Build a backtesting module in `notebooks/` or `scripts/`:

1. For each completed game week in the `plate_appearances` table, reconstruct the ELO states as of the Monday of that week (use `talent_daily_ohlc.open_elo` for that date).
2. Run `predict_plate_appearance` with those ELOs.
3. Compare predicted probabilities to actual `result_type` distributions for that week.
4. Compute per-player and aggregate metrics: Brier score, log-loss, calibration curve (predicted P(HR) vs actual HR rate in decile bins).
5. Compute fantasy point prediction error: predicted weekly points vs actual weekly points (requires a mapping from result_types back to ESPN points, which `fantasy_calculator.py` already provides).

**Why it helps:**
This is the prerequisite infrastructure for all other improvements. Without a backtesting harness, any change to divisors, clutch weights, or form adjustments cannot be objectively validated. It converts the system from "informed intuition" to "data-driven iteration."

**Files:** New `notebooks/backtest_projections.ipynb` or `scripts/backtest.py`; touches `src/fantasy/matchup_predictor.py` and `src/fantasy/fantasy_calculator.py` (read-only).

**Complexity:** Large.

---

## Calibration / Validation

How to measure whether each improvement actually made predictions better:

### Primary Metrics

**1. Point prediction MAE (main signal)**
- Compare `expected_points` from `BatterProjection.total_points` vs actual ESPN points scored that week.
- Compute per-player MAE and week-over-week variance. Target: reduce week-level MAE by >10% vs baseline.
- This requires linking `plate_appearances.result_type` → ESPN points via the same `fantasy_calculator` logic.

**2. Probability calibration (Brier score)**
- For each PA outcome (BB, K, 1B, 2B, 3B, HR), compute the Brier score:
  `BS = mean((predicted_prob - actual_outcome)^2)`
- A well-calibrated model should produce: when it predicts P(HR)=0.05, roughly 5% of those PAs actually result in HRs.
- Plot calibration curves in decile bins. Current model likely overestimates extreme players.

**3. Rank correlation (Spearman rho)**
- The primary fantasy use case is ranking players for roster decisions.
- Spearman rho between predicted weekly points rank and actual rank. Target: rho > 0.60 for batters, > 0.55 for pitchers (both harder to predict).

### Per-Improvement Validation

| Improvement | Validation approach |
|---|---|
| QW-1 Clutch in win prob | Compare SP win probability vs actual win% split by clutch ELO quartile |
| QW-2 Pitcher in Stage 3 | Compare predicted HR rate vs actual HR rate split by pitcher stuff quartile |
| QW-3 Career/season blend | Compare cold-start players (<100 PA season) MAE before/after |
| QW-4 Fangraphs IP per start | Compare predicted IP vs actual IP; should eliminate systematic +/- bias |
| ME-1 OHLC form | Compare week-1 accuracy vs players with high OHLC volatility in prior week |
| ME-3 Home/away | Compare home game prediction error vs away game prediction error |
| LR-1 Divisor calibration | Log-loss on held-out 20% of PAs from `plate_appearances`; compare to baseline |
| LR-2 XBH split model | Compare predicted 2B/3B/HR ratios vs actual ratios by speed/power ELO quartile |

### Minimum Viable Backtesting Setup

Before implementing any large rework:

1. Pull 4 complete weeks of `plate_appearances` data (minimum).
2. For each PA, join `talent_player_current` on `batter_id` and `pitcher_id` to get ELOs.
3. Run `predict_plate_appearance(batter_elo, pitcher_elo)` for each row.
4. Compute baseline Brier score and log-loss.
5. Store as `notebooks/backtest_baseline.ipynb` with committed output.

Every subsequent change must beat these baseline numbers on held-out weeks before being merged.

### Red Flags to Watch

- If predicted BB rate is consistently > 12% for any batter, the discipline ELO normalization is off (`BATTER_DISCIPLINE` mean=1700.3, std=139 — the widest distribution by far, making z-scores volatile).
- If predicted HR rate for top-power batters exceeds 10% per PA, Stage 3 divisor (5.0) is too small.
- If week-level point prediction MAE is higher for players with <100 season PAs, the career/season blend (QW-3) is the highest-priority fix.
