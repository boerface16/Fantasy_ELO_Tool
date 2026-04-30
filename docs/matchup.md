# Matchup Prediction Engine: A Comprehensive Technical Reference

**Fantasy Matchup Predictor — Internal Documentation**
*Baseball Analytics Series, Vol. 2*

---

## Table of Contents

1. [Introduction and Philosophy](#1-introduction-and-philosophy)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Inputs: Talent ELO Z-Scores](#3-inputs-talent-elo-z-scores)
   - 3.1 [ELO Distributions and Z-Score Normalization](#31-elo-distributions-and-z-score-normalization)
   - 3.2 [Career vs. Season ELO Blending](#32-career-vs-season-elo-blending)
   - 3.3 [Data Lookup Pipeline](#33-data-lookup-pipeline)
4. [The 3-Stage Prediction Model](#4-the-3-stage-prediction-model)
   - 4.1 [Stage 1: Softmax — Walk, Strikeout, or Ball in Play?](#41-stage-1-softmax--walk-strikeout-or-ball-in-play)
   - 4.2 [LR-3: HBP Split from Walk Probability](#42-lr-3-hbp-split-from-walk-probability)
   - 4.3 [Stage 2: Logistic — Hit or Out on a Ball in Play?](#43-stage-2-logistic--hit-or-out-on-a-ball-in-play)
   - 4.4 [ME-3: Home Field Logit Adjustment](#44-me-3-home-field-logit-adjustment)
   - 4.5 [Stage 3: XBH Probability — What Kind of Hit?](#45-stage-3-xbh-probability--what-kind-of-hit)
   - 4.6 [Dynamic 2B/3B/HR Split](#46-dynamic-2b3bhr-split)
   - 4.7 [Final Probability Assembly](#47-final-probability-assembly)
5. [League Average Baselines](#5-league-average-baselines)
6. [Output: PA Outcome Probabilities and Expected wOBA](#6-output-pa-outcome-probabilities-and-expected-woba)
7. [Fantasy Point Estimation](#7-fantasy-point-estimation)
   - 7.1 [ESPN H2H Scoring Rules](#71-espn-h2h-scoring-rules)
   - 7.2 [Batter Point Projection](#72-batter-point-projection)
   - 7.3 [Pitcher Point Projection](#73-pitcher-point-projection)
   - 7.4 [Stolen Base Estimation](#74-stolen-base-estimation)
8. [Weekly Projection Pipeline](#8-weekly-projection-pipeline)
   - 8.1 [Roster Parsing](#81-roster-parsing)
   - 8.2 [Schedule and Probable Pitcher Fetching](#82-schedule-and-probable-pitcher-fetching)
   - 8.3 [Opponent Resolution](#83-opponent-resolution)
   - 8.4 [Per-Game Aggregation and Scaling](#84-per-game-aggregation-and-scaling)
   - 8.5 [Optimal Lineup Construction](#85-optimal-lineup-construction)
9. [API Endpoints: The Matchup Tab](#9-api-endpoints-the-matchup-tab)
10. [Model Calibration](#10-model-calibration)
11. [Validation and Backtesting](#11-validation-and-backtesting)
12. [Known Limitations and Future Work](#12-known-limitations-and-future-work)

---

## 1. Introduction and Philosophy

The matchup prediction engine answers one very specific question: **given a specific batter and a specific pitcher, what is the probability distribution over all plate appearance outcomes for their next at-bat?**

This sounds like a statistics textbook problem, but it's actually a deeply non-trivial challenge. MLB hitters average roughly 3.9 plate appearances per game, and across a 162-game season that means each player has about 630 PAs. In a fantasy matchup week, a batter might face 12–20 total PAs against a rotation of 3–6 different pitchers. Accurately predicting those outcomes requires capturing not just "how good is this batter?" and "how good is this pitcher?" but the specific *interaction* between their skill profiles.

A high-contact, low-power batter facing a flyball pitcher who gives up weak contact looks completely different from a high-power slugger facing a groundball-inducing specialist. The expected outcomes are radically different even if all four players have the same composite ELO. **Dimension-specific matchup analysis is the only way to capture this correctly.**

The approach in this system draws from three intellectual traditions:

1. **Logistic regression / softmax classification** — Converting continuous rating signals into calibrated outcome probabilities.
2. **Sabermetric decomposition** — Breaking the PA into sequential decision trees (BB/K/BIP → H/Out → 1B/XBH → 2B/3B/HR) that mirror the actual structure of baseball outcomes.
3. **ELO competitive ratings** — Using the 9-dimensional talent ELO ratings (see `docs/elo.md`) as the underlying player-quality signals.

The result is a **3-stage probability tree** that produces a full distribution over {BB, HBP, K, OUT, 1B, 2B, 3B, HR} for every batter-pitcher combination, every time it's called.

---

## 2. System Architecture Overview

```
                    INPUTS
         ┌──────────────────────────┐
         │  Batter Talent ELO       │  (contact, power, discipline, speed, clutch)
         │  Pitcher Talent ELO      │  (stuff, bip_suppression, command, clutch)
         │  Is Home Game?           │
         └──────────┬───────────────┘
                    │
              Z-SCORE NORMALIZATION
         (per-dimension mean/std from config)
                    │
         ┌──────────▼───────────────┐
         │    3-STAGE PREDICTION    │
         │                          │
         │  Stage 1: Softmax        │  BB vs K vs BIP
         │    + LR-3: HBP split     │
         │  Stage 2: Logistic       │  H vs Out | BIP
         │    + ME-3: home shift    │
         │  Stage 3: Logistic       │  XBH vs 1B | Hit
         │    + Dynamic 2B/3B/HR    │
         └──────────┬───────────────┘
                    │
               PROBABILITIES
         {BB, HBP, K, OUT, 1B, 2B, 3B, HR}
                    │
         ┌──────────▼───────────────┐
         │  FANTASY POINT ESTIMATOR │
         │  (ESPN H2H scoring)      │
         └──────────────────────────┘
```

The entry point is `src/fantasy/matchup_predictor.py`, class `MatchupPredictor`, method `predict_plate_appearance(batter_elo, pitcher_elo, is_home)`.

---

## 3. Inputs: Talent ELO Z-Scores

### 3.1 ELO Distributions and Z-Score Normalization

The prediction model doesn't operate on raw ELO values (e.g., "Contact ELO = 1523") — it operates on **z-scores**, which express a player's rating in terms of standard deviations above or below the population mean. This normalization is critical for two reasons:

1. Each talent dimension has a different mean and standard deviation due to its distinct K-factor, scale, and event frequency. Contact ELO clusters tightly (low std) while Discipline ELO spans a wide range (high std). Raw values aren't comparable across dimensions.
2. The logit/softmax transformation requires inputs centered near zero to produce well-calibrated probability shifts.

The population parameters (mean and std) for each dimension are stored in `config/multi_elo_config.yaml` and were estimated from the observed distribution of player ELOs after a full season of accumulation:

| Dimension | Mean | Std |
|---|---|---|
| Batter — Contact | 1504.5 | 33.9 |
| Batter — Power | 1468.6 | 61.6 |
| Batter — Discipline | 1700.3 | 139.0 |
| Batter — Speed | 1500.0 | 50.0 |
| Pitcher — Stuff | 1587.3 | 56.6 |
| Pitcher — BIP Suppression | 1513.3 | 18.2 |
| Pitcher — Command | 1681.1 | 126.5 |
| Pitcher — Clutch | 1500.0 | 61.7 |

The z-score for each dimension:

```
z_contact    = (batter_contact_elo    − 1504.5) / 33.9
z_power      = (batter_power_elo      − 1468.6) / 61.6
z_discipline = (batter_discipline_elo − 1700.3) / 139.0
z_speed      = (batter_speed_elo      − 1500.0) / 50.0
z_stuff      = (pitcher_stuff_elo     − 1587.3) / 56.6
z_bip        = (pitcher_bip_elo       − 1513.3) / 18.2
z_command    = (pitcher_command_elo   − 1681.1) / 126.5
```

A batter with z_contact = +1.5 is 1.5 standard deviations above the average MLB contact hitter — roughly the 93rd percentile. This is the signal the model uses.

### 3.2 Career vs. Season ELO Blending

When a player has fewer than `reliability_threshold` relevant events in the current season, the lookup layer (`EloLookup`) automatically blends season and career ELO before normalization:

```
effective_elo[d] = 0.67 × season_elo[d] + 0.33 × career_elo[d]
```

This blend is applied dimension-by-dimension. A player might have a reliable Contact ELO (400+ contact events) but an unreliable Speed ELO (fewer than 50 baserunning events) — in that case, only the Speed dimension is blended with career data.

### 3.3 Data Lookup Pipeline

ELO data is fetched from Supabase in batch to minimize round trips. `EloLookup.load_batch(player_ids)` fetches all current talent ELO rows for a set of player IDs in one query against the `talent_player_current` table. Within a projection session (e.g., one weekly projection run), all lookups are served from the in-memory cache.

For players completely absent from the database (e.g., international prospects just debuted), all dimensions default to their population means, which produce z-scores of 0.0 — league-average predictions for every outcome. The prediction engine degrades gracefully to the league baseline when individual data is unavailable.

---

## 4. The 3-Stage Prediction Model

The model is implemented in `src/fantasy/matchup_predictor.py` (V2.2), method `predict_plate_appearance`. The 3 stages mirror the empirical sequential structure of MLB plate appearance outcomes:

```
Every PA ends in one of:
  Walk (BB) ──────────────────────────────────────────────► RESULT
  Hit by Pitch (HBP) ─────────────────────────────────────► RESULT
  Strikeout (K) ──────────────────────────────────────────► RESULT
  Ball in Play (BIP)
    └─► Hit ─────────────────────────────────────────────► RESULT
    │     └─► Extra-Base Hit (XBH)
    │           └─► Double ──────────────────────────────► RESULT
    │           └─► Triple ──────────────────────────────► RESULT
    │           └─► Home Run ───────────────────────────► RESULT
    └─► Out ─────────────────────────────────────────────► RESULT
```

Each branch is modeled as an independent logistic or softmax function of the relevant z-score differences.

### 4.1 Stage 1: Softmax — Walk, Strikeout, or Ball in Play?

Stage 1 allocates probability across the three main PA outcome categories: walk, strikeout, or ball in play. It uses a **three-way softmax** seeded by league average log-odds and adjusted by batter-pitcher ELO matchup signals.

**Competitive signals used:**

```
z_disc_cmd     = z_discipline − z_command      (batter patience vs. pitcher control)
z_stuff_contact = z_stuff − z_contact          (pitcher stuff vs. batter contact)
```

**Logit formulation:**

```
logit_bb  = log(bb_rate / bip_rate)  +  z_disc_cmd    / D_stage1_bb
logit_k   = log(k_rate  / bip_rate)  +  z_stuff_contact / D_stage1_k
logit_bip = 0.0                       (reference category — the denominator)
```

Where:
- `bb_rate = 0.0949` (MLB 2025 average: 9.49% of PAs end in walks)
- `k_rate = 0.2218` (MLB 2025 average: 22.18% of PAs end in strikeouts)
- `bip_rate = 0.6834` (MLB 2025 average: 68.34% of PAs produce BIP)
- `D_stage1_bb = 3.1266` (z-score divisor for walk discrimination — calibrated)
- `D_stage1_k  = 8.4243` (z-score divisor for strikeout discrimination — calibrated)

**Softmax normalization:**

```
raw_bb  = exp(logit_bb)
raw_k   = exp(logit_k)
raw_bip = 1.0  [=exp(0)]

total = raw_bb + raw_k + raw_bip

P(BB)  = raw_bb  / total
P(K)   = raw_k   / total
P(BIP) = raw_bip / total
```

**Interpretation of divisors:**

The divisor `D_stage1_bb = 3.13` is small, meaning even a modest z-score difference on the Discipline vs. Command axis moves walk probability substantially. A batter at z_disc = +1.0 facing a pitcher at z_cmd = −1.0 (a patient batter vs. a wild pitcher) produces z_disc_cmd = +2.0, shifting the walk logit by 2.0/3.13 ≈ +0.64. That's a meaningful walk probability increase — roughly a 6–8 percentage point jump — consistent with what we observe when a contact-rich batter with no walks faces a command-first pitcher vs. when a walk-heavy batter faces an erratic one.

The strikeout divisor `D_stage1_k = 8.42` is larger, meaning strikeout rates shift more slowly with ELO differences. This reflects the reality that strikeout rates are less sensitive to individual matchup variation: even very high-contact hitters strike out some of the time, and even elite power hitters rarely K above 35%.

### 4.2 LR-3: HBP Split from Walk Probability

After Stage 1 assigns `P(BB)`, a secondary split separates **hit-by-pitch** from true walks. HBP probability is not independently modeled at Stage 1 because it's rare (~1.5% of PAs) and correlated with — but distinct from — walk rate.

```
hbp_fraction = HBP_BASE_FRACTION − z_command × HBP_COMMAND_SCALE
hbp_fraction = clamp(hbp_fraction, 0.0, 0.30)

P(HBP) = P(BB) × hbp_fraction
P(BB)  = P(BB) × (1 − hbp_fraction)
```

Where:
- `HBP_BASE_FRACTION = 0.15` (15% of base-on-balls class events are HBP at league average)
- `HBP_COMMAND_SCALE = 0.03` (per z-score unit of pitcher command)
- Divisor: `D_stage1_hbp = 7.0` (from config, used in the command adjustment)

**Logic:** A pitcher with poor command (z_command = −2.0) is more likely to hit batters:
```
hbp_fraction = 0.15 − (−2.0) × 0.03 = 0.15 + 0.06 = 0.21
```
21% of the walk-class probability goes to HBP instead of 15%.

A pitcher with elite command (z_command = +2.0) is less likely to hit batters:
```
hbp_fraction = 0.15 − 2.0 × 0.03 = 0.15 − 0.06 = 0.09
```

This adjustment is clamped between 0% and 30% to prevent edge cases from producing unreasonable HBP probabilities.

### 4.3 Stage 2: Logistic — Hit or Out on a Ball in Play?

Given that the PA ends in a ball in play (`P(BIP)` from Stage 1), Stage 2 determines whether that ball becomes a hit.

**Competitive signal:**

```
z_contact_bip = z_contact − z_bip_suppression
```

A high-contact batter facing a poor BIP-suppressor produces a positive signal; an average batter facing a groundball specialist produces a negative signal.

**Logit formulation:**

```
base_logit = log(hit_rate_on_bip / (1 − hit_rate_on_bip))
           = log(0.3206 / 0.6794)
           = −0.752

logit_hit = base_logit + z_contact_bip / D_stage2

P(Hit | BIP) = 1 / (1 + exp(−logit_hit))
P(Out | BIP) = 1 − P(Hit | BIP)
```

Where:
- `hit_rate_on_bip = 0.3206` (MLB 2025: 32.06% of balls in play become hits — BABIP)
- `D_stage2 = 20.0` (z-score divisor — calibrated)

**Marginal probabilities:**

```
P(Hit) = P(BIP) × P(Hit | BIP)
P(Out) = P(BIP) × P(Out | BIP)
```

The divisor of 20.0 for Stage 2 is the largest of all three stages, reflecting that BABIP is notoriously noisy. The BIP Suppression ELO does contain real signal (groundball pitchers do suppress BABIP), but the effect per unit of ELO is smaller than for walks or strikeouts. A 1-standard-deviation advantage in contact vs. BIP suppression shifts the hit probability on BIP by only about 1.5 percentage points — modest, but real.

### 4.4 ME-3: Home Field Logit Adjustment

Home teams have a small but real BABIP advantage — home batters are comfortable in their park, understand the quirks of the outfield walls, and may benefit from friendly official scorers. ME-3 adds a fixed logit shift for home batters:

```
if is_home:
    logit_hit += HOME_LOGIT_SHIFT  (= 0.010)
```

This shifts `P(Hit|BIP)` by roughly +0.25 percentage points for home batters — a small but directionally correct adjustment. The value of 0.010 was tuned from historical home vs. away BABIP differentials (~.003 in most seasons).

### 4.5 Stage 3: XBH Probability — What Kind of Hit?

Given that the ball in play became a hit, Stage 3 determines whether it's a single or an extra-base hit (XBH = double, triple, or home run).

**Competitive signal:**

```
z_stuff_power = z_stuff − z_power
```

A power hitter facing a pitcher without elite stuff will produce more extra-base hits. A weak-hitting contact guy facing a high-Stuff pitcher will hit more singles.

**Logit formulation:**

```
base_logit_xbh = log(xbh_rate_on_hit / (1 − xbh_rate_on_hit))
               = log(0.3493 / 0.6507)
               = −0.624

logit_xbh = base_logit_xbh − z_stuff_power / D_stage3

P(XBH | Hit) = 1 / (1 + exp(−logit_xbh))
P(1B  | Hit) = 1 − P(XBH | Hit)
```

Where:
- `xbh_rate_on_hit = 0.3493` (MLB 2025: 34.93% of hits are XBH)
- `D_stage3 = 16.4052` (calibrated)

Note the **negative** sign before the z-score: `z_stuff_power = z_stuff − z_power`. When stuff > power (pitcher advantage), this is positive, and subtracting it *reduces* the XBH logit. When power > stuff (batter advantage), this is negative, and subtracting a negative value *increases* the XBH logit. The sign convention ensures that batter power advantage increases XBH probability.

**Marginal probabilities:**

```
P(XBH) = P(Hit) × P(XBH | Hit)
P(1B)  = P(Hit) × P(1B  | Hit)
```

### 4.6 Dynamic 2B/3B/HR Split

Stage 3 tells us the probability of an extra-base hit, but not which type. The split across doubles, triples, and home runs uses **dynamic ratio calculation** driven by batter power and speed, and pitcher stuff:

```
hr_raw = max(0.0, HR_BASE + z_power × POWER_HR_SCALE − z_stuff × STUFF_HR_SCALE)
3b_raw = max(0.0, 3B_BASE + z_speed × SPEED_3B_SCALE)
2b_raw = 2B_BASE  (league average residual — treated as anchor)
```

Parameters from `multi_elo_config.yaml`:
- `HR_BASE = 0.403`   (40.30% of XBH are home runs at league average)
- `3B_BASE = 0.0448`  (4.48% of XBH are triples)
- `2B_BASE = 0.5522`  (55.22% of XBH are doubles)
- `POWER_HR_SCALE = 0.03`  (per z-score unit of batter power)
- `STUFF_HR_SCALE = 0.03`  (per z-score unit of pitcher stuff)
- `SPEED_3B_SCALE = 0.008` (per z-score unit of batter speed)

Normalize to sum to 1.0:

```
total = hr_raw + 3b_raw + 2b_raw

hr_ratio = hr_raw / total
3b_ratio = 3b_raw / total
2b_ratio = 2b_raw / total
```

**Final XBH probabilities:**

```
P(HR) = P(XBH) × hr_ratio
P(3B) = P(XBH) × 3b_ratio
P(2B) = P(XBH) × 2b_ratio
```

**Why dynamic rather than fixed:** Home run rate varies significantly by player power profile and pitcher type. A dead-pull power hitter against a fastball-heavy pitcher who leaves pitches elevated will have dramatically higher HR probability than a line-drive contact hitter facing a sinkerball specialist — even if both matchups produce the same overall XBH probability. The dynamic split captures this without requiring a separate model stage.

### 4.7 Final Probability Assembly

After all three stages plus the two adjustment layers, the final output is:

```python
{
    'BB':  P_bb,             # True walk (post HBP-split)
    'HBP': P_hbp,            # Hit by pitch
    'K':   P_k,              # Strikeout
    'OUT': P_out,            # Out on BIP (includes GIDP, FC, sac fly, etc.)
    '1B':  P_1b,             # Single
    '2B':  P_2b,             # Double
    '3B':  P_3b,             # Triple
    'HR':  P_hr              # Home run
}
```

Verification that probabilities sum to 1.0 is enforced. No probability is allowed to be negative (the clamp in each stage ensures this).

The output also includes diagnostic fields:
```python
{
    'z_diffs': {
        'disc_cmd':        z_disc_cmd,
        'stuff_contact':   z_stuff_contact,
        'contact_bip':     z_contact_bip,
        'stuff_power':     z_stuff_power
    },
    'stages': {
        'stage1': {'P_bb_raw': ..., 'P_k_raw': ..., 'P_bip_raw': ...},
        'stage2': {'P_hit_given_bip': ..., 'logit': ...},
        'stage3': {'P_xbh_given_hit': ..., 'logit': ...}
    },
    'expected_woba': float
}
```

---

## 5. League Average Baselines

All baseline rates are calibrated to the 2025 MLB regular season. They are stored in `matchup_predictor.py` as module-level constants and in `config/multi_elo_config.yaml` for configurability.

| Statistic | Value | Meaning |
|---|---|---|
| `bb_rate` | 9.49% | Fraction of PAs ending in walk |
| `k_rate` | 22.18% | Fraction of PAs ending in strikeout |
| `bip_rate` | 68.34% | Fraction of PAs producing a ball in play |
| `hit_rate_on_bip` | 32.06% | BABIP — fraction of BIP becoming hits |
| `xbh_rate_on_hit` | 34.93% | Fraction of hits that are XBH |
| `2b_ratio` | 55.22% | Fraction of XBH that are doubles |
| `3b_ratio` | 4.48% | Fraction of XBH that are triples |
| `hr_ratio` | 40.30% | Fraction of XBH that are home runs |

When a batter and pitcher both have league-average ELO (z-scores = 0 for all dimensions), the model produces exactly these league-average rates. This is the fundamental invariant of the calibration: the model is a **skill-relative adjustment** on top of a correctly-specified league baseline, not a standalone probability generator.

---

## 6. Output: PA Outcome Probabilities and Expected wOBA

The expected wOBA for a matchup is computed from the probability vector using the standard wOBA weights (2025 season):

```
E[wOBA] = wOBA_BB × P(BB)
         + wOBA_HBP × P(HBP)
         + wOBA_1B × P(1B)
         + wOBA_2B × P(2B)
         + wOBA_3B × P(3B)
         + wOBA_HR × P(HR)
```

Standard wOBA weights (2025):
- Walk: 0.690
- HBP: 0.720
- Single: 0.880
- Double: 1.254
- Triple: 1.583
- Home run: 2.031

This expected wOBA is displayed prominently in the matchup UI as a single-number summary of the matchup quality, but the full probability vector is what drives fantasy point estimation.

---

## 7. Fantasy Point Estimation

### 7.1 ESPN H2H Scoring Rules

The system implements ESPN head-to-head points league scoring from `config/espn_scoring.yaml`:

**Batter scoring:**

| Stat | Points |
|---|---|
| Total Bases (TB) | +1 per base |
| Runs (R) | +1 |
| RBIs | +1 |
| Walks (BB) | +1 |
| Stolen Bases (SB) | +1 |
| Strikeouts (SO) | −1 |
| Errors committed | −3 |

**Pitcher scoring:**

| Stat | Points |
|---|---|
| Innings Pitched | +3 per IP |
| Strikeouts | +1 |
| Wins | +5 |
| Saves | +5 |
| Hits allowed | −1 |
| Earned Runs | −1 |
| Home Runs allowed | −1 |
| Walks issued | −1 |
| Hit Batsmen | +1 |
| Losses | −5 |
| Blown Saves | −5 |
| Balks | −10 |
| Complete Games | +3 |
| Shutouts | +5 |
| Pickoffs | +2 |

### 7.2 Batter Point Projection

The batter fantasy point estimator (`fantasy_calculator.py`, method `estimate_batter_points`) converts a PA probability vector into expected fantasy points per plate appearance, then scales by the expected number of PAs in a game (default 3.9):

**Expected Total Bases per PA:**

```
E[TB] = P(1B) × 1  +  P(2B) × 2  +  P(3B) × 3  +  P(HR) × 4
```

**Expected Run components:**

```
E[Runs]  = E[TB] × r_per_tb   +  z_speed × speed_run_scale
         = E[TB] × 0.40       +  z_speed × 0.015

E[RBIs]  = E[TB] × rbi_per_tb
         = E[TB] × 0.45
```

The run and RBI scaling factors (0.40 per TB and 0.45 per TB) come from `config/espn_scoring.yaml` calibration section. These are regression coefficients derived from historical batter-level data: for every total base a batter accumulates, they historically score about 0.40 runs and drive in about 0.45 RBIs (after accounting for contextual factors like batting order position and team quality). The speed adjustment on runs (`z_speed × 0.015`) reflects that faster players score more runs per hit by taking extra bases on hits by teammates and scoring from further back on singles.

**Expected Walk points:**

```
E[Walk points] = P(BB)
```

(Walks are worth +1 point in ESPN scoring, so the probability of a walk is also the expected walk points per PA.)

**Expected Strikeout penalty:**

```
E[SO penalty] = −P(K)
```

**Total per-PA expected points:**

```
E[Points/PA] = E[TB] × 1
             + E[Runs] × 1
             + E[RBIs] × 1
             + E[Walk points]
             + E[SB points]          (see §7.4)
             + E[SO penalty]
```

**Scale to per-game:**

```
E[Points/Game] = E[Points/PA] × pas_per_game
```

Where `pas_per_game = 3.9` (MLB average PA per game per batter, accounting for incomplete lineups and doubleheaders).

### 7.3 Pitcher Point Projection

The pitcher fantasy point estimator (`estimate_pitcher_points`) is called separately for each projected start.

**Inputs:** PA probability vector (from the matchup predictor, treating the pitcher as the subject), projected innings pitched, win probability, loss probability.

**Expected stat lines per inning (using ~4.3 batters faced per inning):**

```
BFP_per_inning = 4.3

E[K]  = P(K)   × innings × BFP_per_inning
E[H]  = P(Hit) × innings × BFP_per_inning
E[HR] = P(HR)  × innings × BFP_per_inning
E[BB] = P(BB)  × innings × BFP_per_inning
E[HB] = P(HBP) × innings × BFP_per_inning
```

**Expected Earned Runs (simplified ERA model):**

```
E[ER] = (E[H] + E[BB] + E[HB]) × ER_per_baserunner
      = (E[H] + E[BB] + E[HB]) × 0.30
```

The 0.30 factor means roughly 30% of baserunners eventually score — a reasonable league-average assumption that avoids the complexity of a full base-path model.

**Expected fantasy points per start:**

```
E[Points] = innings × 3               (IP points)
           + E[K]   × 1               (strikeout points)
           + E[H]   × (−1)            (hits allowed)
           + E[ER]  × (−1)            (earned runs)
           + E[HR]  × (−1)            (home runs allowed)
           + E[BB]  × (−1)            (walks issued)
           + E[HB]  × 1               (hit batsmen — positive in ESPN scoring)
           + win_prob  × 5             (expected win points)
           + loss_prob × (−5)          (expected loss points)
```

Win/loss probabilities are currently assumed to be symmetric (win_prob = 0.50 for an average team facing an average opponent). Future work includes using team ELO to generate game-specific win probabilities.

**Reliever projection** (`estimate_reliever_points`) follows the same logic but scales by appearances per week rather than starts, with shorter per-appearance inning totals and includes save/blown-save probability for closers.

### 7.4 Stolen Base Estimation

Stolen bases are the trickiest per-PA statistic to project because they depend on:
1. The batter's speed and baserunning aggressiveness
2. The pitcher's delivery time and pickoff tendency
3. The catcher's arm
4. Managerial strategy

The current model estimates SB probability using a simplified model:

```
on_base_probability = P(1B) + P(BB) + P(HBP)
                    (situations where a runner is on 1st and could steal 2nd)

speed_factor = 1.0 + max(0, z_speed) × SB_SPEED_SCALE  (z_speed floored at 0)

pitcher_sb_factor = 1.0  (currently league-average; future: use pitcher SB-allowed rate)

E[SB/PA] = on_base_probability × SB_BASE_RATE × speed_factor × pitcher_sb_factor
         = on_base_probability × 0.02 × speed_factor × 1.0
```

The base SB rate of 0.02 per on-base event is the MLB 2025 league average stolen base attempt rate (accounting for the new 2023 rules making the running game more viable). The speed z-score boosts this for fast runners.

This is acknowledged as the weakest component of the fantasy point estimator. Future improvements include per-pitcher SB-allowed rates (from MLB Stats API) and a more nuanced "steal opportunity" model.

---

## 8. Weekly Projection Pipeline

The weekly projection system (`src/fantasy/weekly_projection.py`) orchestrates the complete journey from an ESPN roster paste to a ranked projection table with optimal lineup.

### 8.1 Roster Parsing

The user pastes their ESPN roster as text. The `RosterParser` (`roster_parser.py`) extracts:

- **Player name:** Fuzzy-matched against the `players` table in Supabase (using string similarity thresholds to handle typos, nicknames, and first-last abbreviations)
- **Team:** Three-letter MLB team code
- **Slot:** Position slot (C, 1B, 2B, SS, 3B, MI, CI, OF, UTIL, SP, RP, BN, IL, NA)
- **Eligible positions:** From the player's registered position(s) in the players table

Fuzzy matching is necessary because ESPN displays names differently from MLB Stats API (e.g., "Yordan Alvarez" vs. "Y. Alvarez"), and user pasting errors are common.

**Known limitation:** The roster parser currently does not reliably resolve batter names to their Statcast MLB player IDs, which means batter ELO lookups fall back to league defaults. This is the highest-priority fix in the backlog.

### 8.2 Schedule and Probable Pitcher Fetching

The schedule fetcher (`schedule_fetcher.py`) calls the MLB Stats API:

```
GET https://statsapi.mlb.com/api/v1/schedule
    ?startDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
    &sportId=1
    &hydrate=probablePitcher
```

This returns all games for the projection week with probable pitchers. For each game, we extract:
- `game_date`, `home_team`, `away_team`, `game_pk`
- `probable_pitcher_name`, `probable_pitcher_id` (MLB Stats API ID, which maps to Statcast `pitcher` column)

Only SP (starting pitchers) have probable pitchers listed. Relief pitchers and bullpen arms do not appear, which is why RP fantasy projections default to 0 appearances — a known limitation described in §12.

### 8.3 Opponent Resolution

`OpponentResolver` (`opponent_resolver.py`) cross-references the roster with the schedule:

For each batter on the roster:
1. Find all games where their team plays during the projection week.
2. For each game, look up the opposing team's probable starting pitcher.
3. Create a `GameMatchup` object: {batter, game_date, opposing_pitcher_id, is_home}.

For each pitcher on the roster:
1. Find games where they are the probable starter.
2. For each game, look up the opposing lineup (currently simplified to league-average).

Active roster slots (BN = bench, active) and inactive slots (IL, NA) are handled:
- **IL/NA slots:** Player is excluded from projections entirely.
- **BN slots:** Player is projected but marked as benchable.

### 8.4 Per-Game Aggregation and Scaling

For each batter-game matchup:

```python
probs = matchup_predictor.predict_plate_appearance(
    batter_elo=elo_lookup.get_batter_elo(batter_id),
    pitcher_elo=elo_lookup.get_pitcher_elo(pitcher_id),
    is_home=game.is_home
)

points_this_game = fantasy_calculator.estimate_batter_points(
    probs=probs,
    pas=3.9,  # average PAs per game
    speed_z=z_speed
)
```

The per-game projection is recorded as a `GameMatchup` object. Summing across all games in the week yields the weekly total:

```
weekly_total = sum(game.expected_points for game in batter.games)
points_per_game = weekly_total / len(batter.games)
```

### 8.5 Optimal Lineup Construction

After projecting all players, the system constructs the **optimal ESPN lineup** using a greedy position-filling algorithm:

ESPN H2H points leagues use these lineup slots:
- **C** (1), **1B** (1), **2B** (1), **SS** (1), **3B** (1)
- **MI** (1 — middle infielder: 2B or SS)
- **CI** (1 — corner infielder: 1B or 3B)
- **OF** (5)
- **UTIL** (1 — any position except pitcher)
- **SP** (5 or configurable)
- **RP** (4 or configurable)

The algorithm:
1. Sort all projected batters by `total_points` descending.
2. Greedily fill each required slot with the highest-projected eligible player not yet slotted.
3. Multi-position eligible players (e.g., 2B/SS) are first assigned to the slot where they provide the most marginal value.
4. Any remaining rostered player can fill UTIL.

This is a simplified heuristic — a true optimal solution would require integer programming — but for typical 25-player rosters, the greedy approach produces near-optimal results.

---

## 9. API Endpoints: The Matchup Tab

The matchup tab on the website is powered by three FastAPI endpoints in `src/api/routers/matchup.py`:

### `GET /matchup/batter/{player_id}/talent`

Returns the talent ELO profile for a batter, formatted for display:

```json
{
  "playerId": 665742,
  "fullName": "Yordan Alvarez",
  "team": "HOU",
  "contact": 1541.2,
  "power": 1598.7,
  "discipline": 1823.4,
  "speed": 1421.0,
  "clutch": 1567.8,
  "compositeElo": 1582.3,
  "paCount": 412
}
```

### `GET /matchup/pitcher/{player_id}/talent`

Returns the talent ELO profile for a pitcher:

```json
{
  "playerId": 477132,
  "fullName": "Justin Verlander",
  "team": "HOU",
  "stuff": 1634.1,
  "bipSuppression": 1521.0,
  "command": 1748.6,
  "clutch": 1512.3,
  "compositeElo": 1634.2,
  "bfpCount": 389
}
```

### `GET /matchup/predict/{batter_id}/{pitcher_id}`

The core prediction endpoint. Fetches both players' talent ELO from Supabase, runs the 3-stage prediction model, and returns:

```json
{
  "batterId": 665742,
  "pitcherId": 477132,
  "probabilities": {
    "BB": 0.1132,
    "HBP": 0.0134,
    "K": 0.2018,
    "OUT": 0.4421,
    "1B": 0.1147,
    "2B": 0.0612,
    "3B": 0.0041,
    "HR": 0.0495
  },
  "expectedWoba": 0.3847,
  "zScoreDiffs": {
    "disc_cmd": 0.72,
    "stuff_contact": -0.34,
    "contact_bip": 0.18,
    "stuff_power": -1.23
  },
  "expectedFantasyPoints": 4.82,
  "stages": { ... }
}
```

The fantasy calculator is also run server-side so the UI can display expected fantasy points directly without requiring a client-side calculation.

---

## 10. Model Calibration

The ZSCORE_DIVISOR values are the most important calibration parameters in the prediction engine — they control how sensitively the model responds to ELO differences. These were estimated via **log-loss minimization** in `notebooks/calibrate_divisors.ipynb`.

### Calibration Methodology

1. **Dataset:** Full 2025 regular season PA records from the `plate_appearances` table (183,000+ PAs), with outcomes known.
2. **Feature construction:** For each PA, fetch the batter and pitcher talent ELO ratings as of the day *before* the game (using the `elo_pa_detail` `elo_before` values to prevent look-ahead bias).
3. **Target:** One-hot encoded PA outcomes across {BB+HBP, K, BIP→Hit, BIP→Out}.
4. **Calibration approach:** Grid search over divisor values in the range:
   - `D_stage1_bb`: [1.0, 10.0] in steps of 0.5
   - `D_stage1_k`: [3.0, 20.0] in steps of 0.5
   - `D_stage2`: [5.0, 50.0] in steps of 2.5
   - `D_stage3`: [5.0, 40.0] in steps of 2.5
5. **Loss function:** Multi-class log-loss (cross-entropy) on a held-out test set (last 4 weeks of season).
6. **Result:** The calibrated divisors that minimize log-loss on the test set:

| Parameter | Calibrated Value | Interpretation |
|---|---|---|
| `D_stage1_bb` | 3.1266 | Walk rate is highly sensitive to Disc/Cmd matchup |
| `D_stage1_k` | 8.4243 | Strikeout rate is moderately sensitive to Stuff/Contact matchup |
| `D_stage2` | 20.0 | BABIP is weakly sensitive to Contact/BIP matchup |
| `D_stage3` | 16.4052 | XBH rate is moderately sensitive to Power/Stuff matchup |
| `D_stage1_hbp` | 7.0 | HBP fraction moderately sensitive to pitcher command |

**Why different sensitivities?** The calibration reveals something genuinely interesting about the game: walk rate is the most "exploitable" by skill matchup (patient hitter vs. wild pitcher = dramatically more walks), while BABIP is the most resistant to skill differences (lucky outcomes wash out the skill signal). This aligns with decades of sabermetric literature on BABIP instability.

---

## 11. Validation and Backtesting

Validation is performed in `notebooks/backtest_baseline.ipynb` using the same 2025 season data with walk-forward validation (training on games through date T, testing on T+1 through T+7).

### Metrics

**Brier Score (probability calibration):**
```
BS = (1/N) × Σ (P_predicted - outcome)²
```
Lower is better. A naive model that always predicts league averages scores approximately 0.19.

**Log-Loss (cross-entropy):**
```
LL = −(1/N) × Σ [outcome × log(P_predicted)]
```
Lower is better. A perfectly calibrated model with the observed probabilities scores approximately 0.58 (irreducible entropy of baseball outcomes).

**Fantasy Point MAE:**
```
MAE = (1/N) × Σ |actual_points - projected_points|
```
The current model achieves roughly ±3.2 points per game — meaning a projection of 12.0 has an expected error band of 12.0 ± 3.2.

### Validation Slices

The backtest is segmented by:
- **Batter talent tier:** Top/middle/bottom third by composite batter ELO — model should perform better for extreme players than average ones
- **Pitcher talent tier:** Same for pitchers
- **Home vs. away:** Verifying the ME-3 home logit adjustment is correctly directioned
- **High-leverage situations:** Verifying clutch ELO matters in 2-out RISP situations

---

## 12. Known Limitations and Future Work

| Limitation | Description | Priority |
|---|---|---|
| **Batter ID resolution** | Roster parser does not resolve batter names to MLB IDs; all batter ELO lookups return league defaults | High |
| **Pitcher ELO in own projections** | The pitcher's own talent ELO is not used in their projected start — only as the opponent in batter projections | High |
| **Reliever projections** | MLB Stats API does not provide probable relievers; RPs receive 0 weekly appearances projected | High |
| **Win/loss probability** | Constant 50/50 for pitcher W/L; team ELO should be used for game-specific win probability | Medium |
| **Stolen base model** | SB estimates use a simplified model with no per-pitcher or per-catcher factors | Medium |
| **Lineup position effects** | No accounting for batting order position (3-hole hitter vs. 9-hole hitter gets different RBI opportunities) | Medium |
| **Platoon splits** | No left/right handedness factor; all matchups use same model regardless of handedness | Medium |
| **Form adjustment (ME-1)** | 7-day OHLC momentum is computed but not integrated into prediction inputs | Low |
| **Ballpark speed adjustment** | No stadium-specific stolen base success rate (turf vs. grass, catcher arm) | Low |
| **Injury/fatigue signals** | No days-rest, pitch-count, or injury status integration | Low |

### What a Complete System Would Add

To bring this system to research-quality completeness, future iterations should incorporate:

1. **Platoon splits:** Left/right handedness dramatically affects matchup outcomes. A left-handed batter facing a lefty pitcher has historically had 30–50 points lower wOBA than against a righty.
2. **True Leverage Index:** Integrating Baseball Reference or FanGraphs LI for Clutch ELO updates rather than the current RISP/outs proxy.
3. **Park factors per outcome type:** A park factor specific to HR vs. 2B (Fenway's Green Monster turns HRs into doubles) rather than a single scoring environment factor.
4. **Historical Statcast backfill:** Running the full ELO pipeline from 2017 (Statcast's first year) to build career ELOs grounded in multi-year history rather than just the most recent season.
5. **Pitcher workload modeling:** Pitchers deep into starts face degraded performance; projected innings should account for this.

---

*This document was written to serve as a definitive reference for the matchup prediction engine and fantasy projection system. For the underlying ELO rating systems that supply its inputs, see `docs/elo.md`.*
