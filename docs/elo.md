# ELO Rating Systems: A Comprehensive Technical Reference

**Fantasy Matchup Predictor — Internal Documentation**
*Baseball Analytics Series, Vol. 1*

---

## Table of Contents

1. [Introduction and Philosophy](#1-introduction-and-philosophy)
2. [Core ELO Rating System (V5.3)](#2-core-elo-rating-system-v53)
   - 2.1 [What Is ELO and Why Use It for Baseball?](#21-what-is-elo-and-why-use-it-for-baseball)
   - 2.2 [Data Source: Statcast](#22-data-source-statcast)
   - 2.3 [The ETL Pipeline: Pitch Events to Plate Appearances](#23-the-etl-pipeline-pitch-events-to-plate-appearances)
   - 2.4 [The ELO Update Formula](#24-the-elo-update-formula)
   - 2.5 [K-Factor Modulation (Layer 1: Event Type)](#25-k-factor-modulation-layer-1-event-type)
   - 2.6 [Physics Modifier (Layer 2: Contact Quality)](#26-physics-modifier-layer-2-contact-quality)
   - 2.7 [Park Factor Adjustment](#27-park-factor-adjustment)
   - 2.8 [RE24 State Normalization](#28-re24-state-normalization)
   - 2.9 [ELO Bounds and Season Resets](#29-elo-bounds-and-season-resets)
   - 2.10 [Daily OHLC Tracking](#210-daily-ohlc-tracking)
   - 2.11 [Database Schema: Core ELO Tables](#211-database-schema-core-elo-tables)
3. [Team ELO System](#3-team-elo-system)
   - 3.1 [Design Principles](#31-design-principles)
   - 3.2 [The Team ELO Formula](#32-the-team-elo-formula)
   - 3.3 [Home Field Advantage](#33-home-field-advantage)
   - 3.4 [Margin of Victory Multiplier](#34-margin-of-victory-multiplier)
   - 3.5 [Season Regression](#35-season-regression)
   - 3.6 [Database Schema: Team ELO](#36-database-schema-team-elo)
4. [Talent ELO System (9-Dimensional)](#4-talent-elo-system-9-dimensional)
   - 4.1 [Motivation: Why Dimensions?](#41-motivation-why-dimensions)
   - 4.2 [Architecture Overview](#42-architecture-overview)
   - 4.3 [The Five Batter Dimensions](#43-the-five-batter-dimensions)
   - 4.4 [The Four Pitcher Dimensions](#44-the-four-pitcher-dimensions)
   - 4.5 [Matchup Pairings (Batter vs. Pitcher Dimensions)](#45-matchup-pairings-batter-vs-pitcher-dimensions)
   - 4.6 [The Talent ELO Update Formula](#46-the-talent-elo-update-formula)
   - 4.7 [Event Weight Architecture](#47-event-weight-architecture)
   - 4.8 [Reliability Ramp](#48-reliability-ramp)
   - 4.9 [Clutch Dimension and Leverage](#49-clutch-dimension-and-leverage)
   - 4.10 [Speed Dimension and Baserunning Events](#410-speed-dimension-and-baserunning-events)
   - 4.11 [Composite ELO Scores](#411-composite-elo-scores)
   - 4.12 [Career vs. Season ELO Blending](#412-career-vs-season-elo-blending)
   - 4.13 [Database Schema: Talent ELO Tables](#413-database-schema-talent-elo-tables)
5. [Configuration Reference](#5-configuration-reference)
6. [Daily Pipeline: How ELO Is Updated](#6-daily-pipeline-how-elo-is-updated)
7. [Model Calibration and Tuning](#7-model-calibration-and-tuning)
8. [Known Limitations and Future Work](#8-known-limitations-and-future-work)

---

## 1. Introduction and Philosophy

Building an ELO system for individual baseball players is a fundamentally different problem than the chess or team-sport applications that made ELO famous. In those contexts, each game is a discrete, zero-sum contest between two fully comparable opponents. Baseball is messier: outcomes depend on the plate appearance result, the game state, the ballpark, the inning, lineup construction, weather, and dozens of other confounding factors. The question this system attempts to answer is: **can a dynamic, event-driven ELO rating capture real player quality in a way that is more responsive than traditional season statistics and more principled than arbitrary composite scores?**

The answer we've arrived at is yes — but only with careful engineering.

This document describes three interconnected ELO systems:

1. **Core ELO** — A single composite rating per player per role (batter or pitcher), updated after every plate appearance using RE24-normalized run expectancy and a two-layer K-modulation scheme. Think of this as the "market price" of a player's overall production.

2. **Team ELO** — A FiveThirtyEight-style win-probability ELO applied at the team level, updated after every game. It serves as a contextual layer for opponent difficulty and schedule-strength adjustments.

3. **Talent ELO** — A 9-dimensional extension that decomposes each player's ability into skill-specific sub-ratings: five for batters (Contact, Power, Discipline, Speed, Clutch) and four for pitchers (Stuff, BIP Suppression, Command, Clutch). These dimensions are updated simultaneously via matched binary competitions and form the backbone of the matchup prediction engine.

All three systems share a common database backend (Supabase/PostgreSQL), are updated nightly by an automated GitHub Actions pipeline, and are served via a FastAPI backend to a React frontend.

---

## 2. Core ELO Rating System (V5.3)

### 2.1 What Is ELO and Why Use It for Baseball?

The ELO rating system was designed by Arpad Elo for chess — a game where two players compete head-to-head, one wins and one loses, and the result updates both players' ratings according to how surprising the outcome was relative to their pre-game expectations. A strong player who beats a weak player barely moves; a weak player who upsets a strong player gains substantially.

For baseball, we adapt this to the **plate appearance (PA)** level. Every PA is a micro-competition between batter and pitcher. Rather than a binary win/lose, the "result" is the run expectancy change (delta\_run\_exp) — a continuous score grounded in empirical probability from decades of play-by-play data. A home run in a bases-loaded situation dramatically shifts run expectancy; a weak groundout in a low-leverage spot barely moves it.

The ELO framework earns its place here for three reasons:

- **Responsiveness:** ELO updates after every PA, so hot streaks and slumps register in real time rather than waiting for a season summary.
- **Zero-sum accounting:** Every run-expectancy point gained by the batter is "taken" from the pitcher's rating, keeping the leaderboard collectively stable.
- **No park/state confounding:** We subtract park factors and RE24 baselines before calculating the ELO delta, so a home run at Coors doesn't get the same credit as one at Oracle Park.

### 2.2 Data Source: Statcast

All core ELO calculations are driven by **Baseball Savant Statcast data**, accessed via the [pybaseball](https://github.com/jldbc/pybaseball) Python library, which wraps the Baseball Savant CSV export API.

Each raw Statcast row represents one **pitch**. The columns we extract are:

| Column | Description |
|---|---|
| `events` | PA-ending event (null for non-terminal pitches) |
| `game_pk` | Unique MLB game identifier |
| `game_date` | Date of the game |
| `batter` | MLB player ID (batter) |
| `pitcher` | MLB player ID (pitcher) |
| `inning`, `inning_topbot` | Inning context |
| `at_bat_number` | Sequence number within game |
| `outs_when_up` | Outs at start of PA (0, 1, 2) |
| `on_1b`, `on_2b`, `on_3b` | Runner occupancy (booleans) |
| `home_team`, `away_team` | Team codes for park factor lookup |
| `bat_score`, `fld_score` | Score at time of PA (for leverage inference) |
| `launch_speed` | Exit velocity in mph |
| `launch_angle` | Launch angle in degrees |
| `estimated_woba_using_speedangle` | xwOBA (contact quality via Statcast models) |
| `delta_run_exp` | Run expectancy change from this event (computed by pybaseball from RE288 matrices) |

We filter to `game_type='R'` (regular season only) before processing, discarding spring training, postseason, and All-Star data to keep the rating pool consistent.

### 2.3 The ETL Pipeline: Pitch Events to Plate Appearances

Raw Statcast is pitch-level; ELO is PA-level. The **`statcast_to_pa.py`** module performs this transformation:

1. **Filter to terminal events** — Keep only rows where `events` is non-null (the final pitch of each PA).
2. **Map events to result types** — Standardize the ~40 raw Statcast event strings into clean result categories:

| Raw Statcast Event | Result Type |
|---|---|
| `single` | `Single` |
| `double` | `Double` |
| `triple` | `Triple` |
| `home_run` | `HR` |
| `strikeout`, `strikeout_double_play` | `StrikeOut` |
| `walk` | `BB` |
| `intent_walk` | `IBB` |
| `hit_by_pitch` | `HBP` |
| `sac_fly`, `sac_bunt` | `SAC` |
| `double_play`, `grounded_into_double_play` | `GIDP` |
| `fielders_choice` | `FC` |
| `field_error` | `E` |
| `stolen_base_2b/3b/home` | `SB` |
| `caught_stealing_2b/3b/home` | `CS` |
| `pickoff_caught_stealing_*` | `PKO` |
| `field_out`, `force_out` | `OUT` → refined to `POPUP` or `GROUNDOUT` via `bb_type` |

3. **Refine OUT sub-types** — For generic `field_out` events, check `bb_type`: if `popup` or `fly_ball` → `POPUP`; if `ground_ball` → `GROUNDOUT`.

4. **Generate PA IDs** — For standard PAs: `pa_id = game_pk × 1000 + at_bat_number`. For baserunning events (SB/CS/PKO) which don't have a batter: `pa_id = game_pk × 1,000,000 + at_bat_number × 1000 + pitch_number`.

5. **Extract runner IDs** — For baserunning events, the `batter` column reflects the runner. Captured into `runner_id`.

The output is a clean DataFrame of one row per PA with all the fields needed for ELO calculation.

### 2.4 The ELO Update Formula

The core update equation (implemented in `src/engine/elo_calculator.py`) is:

```
Δ_elo = K_effective × rv_diff
```

Where:

- **`rv_diff`** = adjusted run expectancy difference (detailed in §2.7–2.8)
- **`K_effective`** = modulated K-factor (detailed in §2.5–2.6)

The batter gains `+Δ_elo`; the pitcher loses `−Δ_elo`. This is zero-sum by construction.

```
batter_elo_new = max(500, batter_elo + Δ_elo)
pitcher_elo_new = max(500, pitcher_elo − Δ_elo)
```

Field errors are a special case: if `result_type == 'E'`, the batter's gain is blocked (`Δ_batter = 0`), but the pitcher still loses ELO (`Δ_pitcher = K_effective × rv_diff`). An error is not the batter's accomplishment.

### 2.5 K-Factor Modulation (Layer 1: Event Type)

Not all plate appearance outcomes carry equal information about player skill. A home run is a harder-to-fake demonstration of ability than a hit-by-pitch. The K-factor is the primary control for how much an event shifts ELO.

**Event-type K-factors (Layer 1):**

| Result Type | K-Factor |
|---|---|
| `HR` | 15.0 |
| `Triple` | 14.0 |
| `Double` | 12.0 |
| `Single` | 10.0 |
| `StrikeOut` | 6.0 |
| `BB` (Walk) | 6.0 |
| `IBB`, `HBP`, `SAC` | 3.0 |
| `E` (Error) | 0.0 (blocked for batter) |
| All others (`OUT`, `FC`, `GIDP`, etc.) | 6.0 |

The rationale:
- **Extra-base hits** receive the highest K because they most unambiguously reflect skill at both ends (power/contact for the batter, stuff/location for the pitcher).
- **Walks and strikeouts** receive a moderate K — they're informative but also noisier (a walk could be a patient AB or just a wild pitcher).
- **HBP, SAC, IBB** receive the lowest K because they contain minimal signal about batter-pitcher competition quality.
- **Errors** do not credit the batter at all: the runner reached base through a defender's mistake, not their own skill.

### 2.6 Physics Modifier (Layer 2: Contact Quality)

The second K-modulation layer uses Statcast's **xwOBA** (expected weighted on-base average, derived from exit velocity and launch angle) to scale the K-factor by the quality of contact.

```
physics_mod = 1.0 + α × ((xwOBA − league_avg_xwOBA) / league_avg_xwOBA)
physics_mod = clamp(physics_mod, 0.7, 1.3)

K_effective = K_base × physics_mod
```

Parameters:
- `α` (PHYSICS_ALPHA) = 0.30
- `league_avg_xwOBA` = 0.315 (2025 season baseline)
- Clamp range: [0.70, 1.30]

**Why this matters:** A well-struck ball that happens to be caught at the warning track still reflects batter quality — the batter hit it hard. Without this layer, a 108-mph lineout receives the same ELO treatment as a 68-mph pop-up groundout. The physics modifier boosts K for above-average contact quality and reduces it for weak contact, capturing the skill signal that the binary `events` column misses.

For events with no xwOBA (walks, HBP, strikeouts), the modifier defaults to 1.0, leaving those events unaffected.

### 2.7 Park Factor Adjustment

Ballparks meaningfully affect run scoring. Coors Field at altitude inflates offense dramatically; Oracle Park in San Francisco's marine layer suppresses fly balls. Without correcting for this, players in hitter-friendly parks accumulate ELO faster through no fault of their own.

The park factor adjustment modifies `delta_run_exp` before computing ELO:

```
park_factor = PARK_FACTORS[home_team]  # loaded from data/mlb_park_factors.csv
adjusted_rv = delta_run_exp − (park_factor − 1.0) × ADJUSTMENT_SCALE
```

Where `ADJUSTMENT_SCALE = 0.1`.

**Data source:** `data/mlb_park_factors.csv` contains 10-year rolling average park factors for all 30 MLB stadiums, indexed by home team code. A park factor of 1.00 is league-average; 1.10 means 10% more run scoring than average; 0.90 means 10% fewer runs.

The subtraction pushes down the run value in high-PF parks (Coors, Great American, Fenway) and pushes up the run value in low-PF parks (Petco, Oracle, T-Mobile). This applies to both batter and pitcher, since their ELO moves are mirror images.

### 2.8 RE24 State Normalization

The same event carries very different run value depending on game state. A two-out, bases-empty single scores no runs and adds modest run expectancy. A no-out, bases-loaded single likely scores a run and dramatically raises expectancy.

We normalize for this by subtracting the **RE24 expected run value for the current base-out state**:

```
state = encode(on_1b, on_2b, on_3b, outs)  # integer 0-23
expected_rv = RE24_BASELINE[state]          # from data/mlb_re24_baseline.csv

rv_diff = adjusted_rv − expected_rv
```

**Data source:** `data/mlb_re24_baseline.csv` contains the mean `delta_run_exp` by base-out state, computed from multiple years of Statcast history. There are 24 distinct states (3 base configurations × 8 base occupancy combinations — wait, 8 base × 3 outs = 24 states).

The logic: if a single in the bases-loaded, no-out state typically produces 0.8 runs of run expectancy change, a batter who records that single shouldn't receive extra ELO credit just because the run value was high — that's the game state doing the work, not the batter. By subtracting the expected value, ELO rewards performance *above the state baseline*.

A positive `rv_diff` means the event was better than typical for that state; a negative `rv_diff` means it underperformed expectation.

### 2.9 ELO Bounds and Season Resets

**Floor:** ELO is clamped at a minimum of 500 for all players:
```
elo_new = max(500, elo + Δ_elo)
```
This prevents extreme negative spirals for struggling players and keeps the rating scale interpretable. The initial ELO for any new player is **1500.0**.

**Season resets (FiveThirtyEight method):** At the start of each new season, ELO ratings are partially regressed toward the mean. This prevents multi-year compounding that would make early-career ratings impossible to overcome, and it reflects the genuine uncertainty at the start of a new season:

```
regressed_prior = 0.67 × prior_season_elo + 0.33 × league_mean_elo
season_start_elo = 0.67 × external_projection + 0.33 × regressed_prior
```

In practice with the current implementation, the batch processor detects season boundaries in the PA chronological stream (when `season_year` changes) and applies the reset formula using the mean of all currently-rated players as `league_mean_elo`.

### 2.10 Daily OHLC Tracking

Borrowing terminology from financial markets, the system tracks each player's ELO as an **Open-High-Low-Close (OHLC)** series — one record per player per day.

```
daily_ohlc:
  open  = ELO at first PA of the day
  high  = maximum ELO reached during the day
  low   = minimum ELO reached during the day
  close = ELO after final PA of the day
  delta = close - open  (computed column)
  range = high - low    (computed column)
```

This allows candlestick chart visualization of ELO trends (available in the frontend) and provides the raw data for a form adjustment feature (ME-1: 7-day momentum, dampened by factor 0.05) used in advanced projections.

### 2.11 Database Schema: Core ELO Tables

```sql
-- Current ELO state per player
CREATE TABLE player_elo (
    player_id       INTEGER PRIMARY KEY,
    composite_elo   FLOAT NOT NULL DEFAULT 1500.0,
    pa_count        INTEGER NOT NULL DEFAULT 0,
    last_game_date  DATE
);

-- PA-level ELO detail (one row per PA, both players)
CREATE TABLE elo_pa_detail (
    pa_id               BIGINT PRIMARY KEY,
    batter_id           INTEGER NOT NULL,
    pitcher_id          INTEGER NOT NULL,
    result_type         TEXT NOT NULL,
    batter_elo_before   FLOAT,
    batter_elo_after    FLOAT,
    pitcher_elo_before  FLOAT,
    pitcher_elo_after   FLOAT,
    batter_delta        FLOAT,
    pitcher_delta       FLOAT
);

-- Daily OHLC per player per role
CREATE TABLE daily_ohlc (
    id          BIGSERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL,
    game_date   DATE NOT NULL,
    elo_type    TEXT NOT NULL,  -- 'COMPOSITE'
    open        FLOAT,
    high        FLOAT,
    low         FLOAT,
    close       FLOAT,
    delta       FLOAT GENERATED ALWAYS AS (close - open) STORED,
    range       FLOAT GENERATED ALWAYS AS (high - low) STORED,
    total_pa    INTEGER DEFAULT 0,
    UNIQUE (player_id, game_date, elo_type)
);
```

---

## 3. Team ELO System

### 3.1 Design Principles

The Team ELO system is a faithful implementation of the [FiveThirtyEight MLB ELO methodology](https://fivethirtyeight.com/methodology/how-our-mlb-predictions-work/), adapted for this project's use case: providing contextual difficulty scores for pitching matchup projections.

Unlike the player ELO system (which updates on every PA), Team ELO updates once per **game**, driven by the final score and margin of victory.

### 3.2 The Team ELO Formula

```
E_home = 1 / (1 + 10^((opponent_elo − team_elo − HFA) / D))
E_away = 1 − E_home

actual_home = 1.0 if home wins else 0.0
actual_away = 1.0 − actual_home

MOV = log(|home_score − away_score| + 1)

Δ_home = K × MOV × (actual_home − E_home)
Δ_away = −Δ_home  [zero-sum]
```

Parameters:
| Parameter | Value | Source |
|---|---|---|
| Initial ELO | 1500.0 | `team_elo_config.yaml` |
| K-factor | 4.0 | `team_elo_config.yaml` |
| Home field advantage (HFA) | 24.0 | `team_elo_config.yaml` |
| ELO divisor (D) | 400.0 | `team_elo_config.yaml` |

### 3.3 Home Field Advantage

The HFA of 24 ELO points is added to the home team's effective rating **only for the expected-score calculation**, not to their stored rating. This means a team rated 1500 playing at home is treated as if rated 1524 when computing win probability against a 1500-rated away team, yielding approximately a 54% win probability — consistent with the historical MLB home field advantage of ~54%.

### 3.4 Margin of Victory Multiplier

A blowout win deserves more ELO credit than a walk-off win, but not infinitely more. The logarithmic MOV multiplier captures this diminishing return:

```
MOV = log(|run_diff| + 1)
```

| Run Differential | MOV Multiplier |
|---|---|
| 1 | 0.69 |
| 3 | 1.39 |
| 5 | 1.79 |
| 10 | 2.40 |

This keeps large blowouts from dominating the ratings while still rewarding convincing wins.

### 3.5 Season Regression

At the start of each MLB season, team ELO ratings are reset using the same FiveThirtyEight formula:

```
season_start_elo = 0.67 × preseason_projection + 0.33 × regressed_prior
regressed_prior  = 0.67 × prior_season_elo + 0.33 × 1505
```

The league mean converges to 1505 (slightly above the initialized 1500 due to rounding in the zero-sum constraint). Teams that finished well carry forward 67% of their earned ELO; teams that struggled regress toward average. This reflects the genuine uncertainty of offseason roster changes without discarding prior information entirely.

### 3.6 Database Schema: Team ELO

```sql
CREATE TABLE team_elo (
    id            BIGSERIAL PRIMARY KEY,
    team_code     TEXT NOT NULL,
    game_date     DATE NOT NULL,
    game_pk       INTEGER NOT NULL,
    elo_before    FLOAT NOT NULL,
    elo_after     FLOAT NOT NULL,
    opponent_code TEXT NOT NULL,
    result        TEXT NOT NULL,  -- 'W' or 'L'
    run_diff      INTEGER NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (team_code, game_date, opponent_code, game_pk)
);
```

Current ELO for each team is derived as the most recent `elo_after` from `team_elo` for each `team_code`.

---

## 4. Talent ELO System (9-Dimensional)

### 4.1 Motivation: Why Dimensions?

The core ELO system produces a single composite number that answers "how valuable has this player been?" That number is excellent for leaderboards and quick comparisons, but it obscures *why* a player is good. A .300 hitter who never walks is a very different player from a .260 hitter with a .380 OBP. Their composite ELO might be similar but their matchup profiles against specific pitchers are completely different.

The Talent ELO system decomposes each player's ability into **five batter dimensions** and **four pitcher dimensions**, each updated independently via separate binary competitions. These granular ratings are the direct inputs to the matchup prediction engine (documented in `matchup.md`).

### 4.2 Architecture Overview

The 9-dimensional system (implemented in `src/engine/multi_elo_engine.py` and coordinated by `src/engine/talent_batch.py`) works as follows:

1. For each PA, determine the result type and game context.
2. Look up the event's **weight vector** — a set of signed scalars indicating how much each dimension should respond to this event.
3. For each active batter dimension, run a **binary ELO competition** against the matched pitcher dimension (using the standard ELO expected-score formula).
4. Compute the delta for each dimension independently.
5. Clamp all resulting ELOs to [500, 3000].
6. Store one detail row per player per dimension per PA.

All nine dimensions are updated simultaneously for every PA. The system maintains separate season and career ELO snapshots for each player-dimension combination.

### 4.3 The Five Batter Dimensions

| Dimension | What It Measures | Primary Events |
|---|---|---|
| **Contact** | Ability to make hard, consistent contact | Singles, Doubles, Triples, HRs (moderate), Strikeouts (negative) |
| **Power** | Raw power — ability to produce extra-base hits and home runs | HRs (heavily weighted), Doubles, Triples |
| **Discipline** | Plate patience and zone recognition | Walks (positive), Strikeouts (moderate negative) |
| **Speed** | Baserunning ability and stolen base success | Stolen Bases (positive), Caught Stealing (negative) |
| **Clutch** | Performance in high-leverage situations | Scaled by Leverage Index; active in RISP/2-out situations |

**Configuration parameters per dimension (from `config/multi_elo_config.yaml`):**

| Dimension | K-Factor | Scale | Reliability Threshold | Expected Divisor |
|---|---|---|---|---|
| Contact | 12.0 | 5.0 | 400 PA | 127.0 |
| Power | 14.4 | 10.0 | 200 PA | 218.0 |
| Discipline | 12.0 | 5.0 | 400 PA | 143.0 |
| Speed | 36.0 | 4.0 | 50 events | 425.0 |
| Clutch | 18.0 | 6.0 | 100 events | 115.0 |

The higher K-factor for Speed (36.0) reflects that stolen-base events are rare — the system must move ratings quickly from limited data. Power has a higher K and scale as well because home runs are the most unambiguous single-PA signal of power skill.

### 4.4 The Four Pitcher Dimensions

| Dimension | What It Measures | Opposes (Batter) |
|---|---|---|
| **Stuff** | Raw pitch quality — velocity, movement, whiff generation | Contact |
| **BIP Suppression** | Ability to generate weak contact on balls in play | Contact (secondary) |
| **Command** | Control and location — limiting free passes | Discipline |
| **Clutch** | High-leverage performance | Clutch |

**Configuration parameters per pitcher dimension:**

| Dimension | K-Factor | Scale | Reliability Threshold | Expected Divisor |
|---|---|---|---|---|
| Stuff | 12.0 | 5.0 | 400 BFP | 132.0 |
| BIP Suppression | 4.0 | 3.0 | 400 BFP | 181.0 |
| Command | 12.0 | 5.0 | 400 BFP | 148.0 |
| Clutch | 18.0 | 6.0 | 100 events | 123.0 |

BIP Suppression carries the lowest K and scale because it operates on a subset of PAs (balls in play only) and the signal is lower — many batted balls are influenced heavily by luck on any single event. The divisor of 181.0 reflects a wider ELO distribution for this dimension, requiring larger differences to move the probability meaningfully.

### 4.5 Matchup Pairings (Batter vs. Pitcher Dimensions)

Each batter dimension is paired with a pitcher dimension for the binary ELO competition:

| Batter Dimension | Pitcher Dimension | Competitive Interpretation |
|---|---|---|
| Contact | Stuff | Can the pitcher generate whiffs and weak contact? |
| Power | BIP Suppression | Can the pitcher limit hard contact and home runs? |
| Discipline | Command | Is the pitcher in the zone, or does the patient batter draw walks? |
| Speed | *(no opponent — baseline 0.5)* | Speed is self-referential; no pitcher dimension opposes it |
| Clutch | Clutch | Who steps up in high-leverage moments? |

The Speed dimension is special: since there is no "pitcher speed dimension," the expected score for a speed-related event is fixed at 0.50, meaning the update is purely based on whether the baserunning event succeeded or failed with no opponent-ELO adjustment.

### 4.6 The Talent ELO Update Formula

For batter dimension *d* matched against pitcher dimension *d'*:

```
E = 1 / (1 + 10^((pitcher_elo[d'] − batter_elo[d]) / divisor[d]))

actual = 1.0  if event_weight[d] > 0  (favorable event for batter)
actual = 0.0  if event_weight[d] < 0  (unfavorable event for batter)
actual = skip  if event_weight[d] == 0 (dimension not relevant to this event)

reliability = clamp(0.3 + 0.7 × (event_count[d] / threshold[d]), 0.3, 1.0)

Δ_batter[d] = K[d] × scale[d] × |event_weight[d]| × (actual − E) × reliability

Δ_pitcher[d'] = −Δ_batter[d]  (zero-sum)

batter_elo[d]_new   = clamp(batter_elo[d] + Δ_batter[d], 500, 3000)
pitcher_elo[d']_new = clamp(pitcher_elo[d'] + Δ_pitcher[d'], 500, 3000)
```

The **`|event_weight[d]|`** term acts as a fractional K-modifier within a dimension — it determines what fraction of the full K-scale this event activates for this dimension. A home run activates 100% of the Power dimension's K (weight = 1.00) but only 20% of the Contact dimension's K (weight = 0.20), because a home run is primarily a power event, not a contact test.

### 4.7 Event Weight Architecture

The event weight system is the heart of the talent ELO design. Every result type maps to a vector of signed weights — one per batter dimension and one per pitcher dimension — stored in `config/multi_elo_config.yaml`.

**Batter event weight examples:**

| Event | Contact | Power | Discipline | Speed | Clutch (base) |
|---|---|---|---|---|---|
| HR | 0.20 | 1.00 | 0.00 | 0.00 | 0.80 |
| Triple | 0.50 | 0.60 | 0.00 | 0.60 | 0.60 |
| Double | 0.60 | 0.50 | 0.00 | 0.10 | 0.50 |
| Single | 0.80 | 0.10 | 0.00 | 0.10 | 0.30 |
| BB | 0.00 | 0.00 | 1.00 | 0.00 | 0.20 |
| StrikeOut | −1.00 | 0.00 | −0.50 | 0.00 | −0.50 |
| OUT | −0.40 | 0.00 | 0.00 | 0.00 | −0.20 |
| IBB | 0.00 | 0.00 | 0.20 | 0.00 | 0.00 |
| HBP | 0.00 | 0.00 | 0.10 | 0.00 | 0.10 |

**Key design choices:**
- A strikeout is primarily a **Contact failure** (−1.00) with secondary Discipline (−0.50) and Clutch (−0.50) implications. It is not a Power event — even power hitters strike out without that reflecting their power.
- A home run is primarily a **Power event** (1.00) with secondary Clutch (0.80) and only minor Contact signal (0.20) — hitting a ball 450 feet doesn't require "contact artistry."
- A walk has **zero Contact or Power weight** — it says nothing about the batter's ability to make contact; it says everything about Discipline.
- Triples receive a significant **Speed weight** (0.60) because reaching third base typically requires elite speed.

**Baserunning event weights (SB/CS):**

| Event | Speed | Clutch (base) |
|---|---|---|
| SB (stolen base) | 1.00 | 0.50 |
| CS (caught stealing) | −1.00 | −0.70 |
| PKO (pickoff caught) | −0.80 | −0.50 |

### Pitcher Event Weights

Pitcher event weights are defined separately from batter weights and operate entirely from the pitcher's perspective: a positive weight means the event benefits the pitcher, and a negative weight means the pitcher lost the exchange. Each result type maps to a signed weight vector across the four pitcher dimensions — Stuff, BIP Suppression, Command, and Clutch — stored alongside the batter weights in `config/multi_elo_config.yaml`. Because the two weight tables are independent, both sets run for every PA: the pitcher's four dimensions update according to pitcher weights while the batter's five dimensions update according to batter weights, with the zero-sum constraint applied within each matched pairing (e.g., batter Contact vs. pitcher Stuff) rather than across the two tables.

| Event | Stuff | BIP Suppression | Command | Clutch (base) |
|---|---|---|---|---|
| StrikeOut | 1.00 | 0.00 | 0.30 | 0.50 |
| BB | 0.00 | 0.00 | −1.00 | −0.70 |
| HBP | 0.00 | 0.00 | −0.80 | −0.30 |
| IBB | 0.00 | 0.00 | −0.30 | −0.20 |
| HR | −0.80 | −0.50 | −0.30 | −0.80 |
| Single | 0.00 | −0.60 | 0.00 | −0.50 |
| Double | 0.00 | −0.80 | 0.00 | −0.60 |
| Triple | 0.00 | −0.90 | 0.00 | −0.70 |
| OUT | 0.00 | 0.40 | 0.15 | 0.30 |
| GIDP | 0.00 | 0.50 | 0.15 | 0.80 |
| FC | 0.00 | 0.30 | 0.15 | 0.40 |
| SAC | 0.00 | 0.20 | 0.00 | −0.30 |
| E | 0.00 | −0.10 | 0.00 | −0.20 |
| POPUP | 0.00 | 0.60 | 0.15 | 0.40 |
| GROUNDOUT | 0.00 | 0.40 | 0.15 | 0.30 |

**Key design choices:**
- **Strikeout is the purest Stuff signal** (1.00) — it is the only pitcher event with zero BIP Suppression involvement because the ball never enters play. The secondary Command credit (0.30) reflects that pitchers who attack the zone and get ahead in counts are the ones most likely to generate strikeouts; it is a smaller credit because command is a means to the strikeout, not the strikeout itself.
- **Walks and HBP penalize Command exclusively** — neither event involves a batted-ball outcome, so Stuff and BIP Suppression remain at 0. BB carries the stiffest Command penalty (−1.00) because an unintentional walk is a clean measure of lost control. HBP is slightly softer (−0.80) because it sometimes reflects an intentionally aggressive fastball inside rather than pure loss of command.
- **IBB is the softest Command penalty** (−0.30) — it is chosen deliberately as a strategic decision, so it carries far less information about a pitcher's ability to throw strikes than an unintentional walk does.
- **HR is the only event that penalizes Stuff directly** (−0.80) — a home run almost always means a hittable pitch in the zone; the pitcher failed to miss bats when it mattered most. It also penalizes BIP Suppression (−0.50) and carries the stiffest Clutch penalty (−0.80), making it the single worst event for a pitcher's overall talent ELO profile.
- **BIP Suppression is the "ball-in-play quality" dimension** — it is zero for strikeouts and walks (ball never in play) and scales with the severity of contact: POPUP +0.60 > OUT/GROUNDOUT +0.40 > FC +0.30 > Single −0.60 > Double −0.80 > Triple −0.90. Home runs are handled separately by Stuff (−0.80) rather than BIP Suppression because they typically reflect pitch quality and location, not fielder positioning or batted-ball luck.
- **Command receives small positive credit on weak contact** — OUT, GROUNDOUT, POPUP, FC, and GIDP all carry command: 0.15. Pitchers who induce weak contact are likely attacking the zone and pitching to contact; the credit is modest because the out is ultimately recorded in the field, not by the pitcher alone.
- **GIDP carries the highest Clutch reward** (0.80 base, clutch_multiplier 2.0) — inducing a double play in a high-leverage situation is the pitcher's equivalent of the clutch home run. SAC is the only positive-outcome event that penalizes Clutch (−0.30): although the batter was retired, runners advanced and the pitcher effectively conceded a strategic out.
- **Errors carry a minimal BIP Suppression penalty** (−0.10) — the pitcher put the ball in play and a fielder made the mistake; the pitch quality signal from the event is low, so only a small negative is applied rather than treating it like a hit.

### 4.8 Reliability Ramp

New players start at 1500.0 for every dimension, but this initial rating carries little information — it's just the prior. The **reliability ramp** scales the K-factor by the fraction of a "full information" sample the player has accumulated for that dimension:

```
reliability = clamp(0.3 + 0.7 × (event_count[d] / threshold[d]), 0.3, 1.0)
```

- **Minimum reliability = 0.30** — even a brand-new player's rating moves (at 30% of full speed).
- **Full reliability = 1.00** — reached at or above `threshold[d]` relevant events.
- Between 0 and threshold: linear ramp from 0.30 to 1.00.

**Example:** A batter has recorded 200 relevant contact events. The Contact dimension threshold is 400.

```
reliability = 0.3 + 0.7 × (200/400) = 0.3 + 0.35 = 0.65
```

Their contact ELO moves at 65% of the full K-scale. This is crucial for call-ups and prospects: their initial ratings are unstable and should shift rapidly, but not so much that a single hot week puts them at 1800.

### 4.9 Clutch Dimension and Leverage

The Clutch dimension is distinct from the others in that it requires a **leverage multiplier** rather than a separate event weight. The formula:

```
clutch_multiplier:
  if LI <= leverage_threshold (2.0):  multiplier = 0.0
  else:                               multiplier = min(max_clutch_multiplier, LI / 2.0)

Additional boosts:
  if RISP (on_2b or on_3b):           multiplier = max(multiplier, 0.5)
  if 2 outs and runners on base:      multiplier = max(multiplier, 0.5)

actual_clutch_delta = base_clutch_weight × clutch_multiplier
```

The practical effect: **Clutch ELO only moves in meaningful ways during high-leverage moments.** A home run in a 10−0 blowout in the 8th inning contributes very little to Clutch ELO because LI ≈ 0.1. The same home run with the tying run on second in the 9th inning of a tie game (LI ≈ 2.8) would trigger a clutch multiplier of 1.4, substantially moving both batters' and pitchers' Clutch ELO.

**Limitation:** Because Statcast does not provide Leverage Index directly in the standard export, LI is currently approximated using the game score differential and RISP/outs as proxies. True LI from Baseball Reference or FanGraphs is not yet integrated.

### 4.10 Speed Dimension and Baserunning Events

Speed is the most self-contained dimension. Since no pitcher dimension directly opposes it, baserunning events use a fixed expected-score of 0.50:

```
E_speed = 0.50 (no opponent ELO adjustment)
Δ_speed = K_speed × scale_speed × |weight_speed| × (actual − 0.50) × reliability
```

For a successful stolen base (`actual = 1.0`):
```
Δ_speed = 36.0 × 4.0 × 1.00 × (1.0 − 0.5) × reliability
         = 72.0 × reliability
```

For a caught stealing (`actual = 0.0`):
```
Δ_speed = 36.0 × 4.0 × 1.00 × (0.0 − 0.5) × reliability
         = −72.0 × reliability
```

At full reliability (1.0), a stolen base moves Speed ELO by +72 points; a caught stealing moves it by −72 points. This is intentionally aggressive because stolen base attempts are rare and each one is a high-stakes commitment. The threshold of just 50 events reflects this: a player with 50 baserunning events has a well-established Speed ELO.

### 4.11 Composite ELO Scores

The 9 individual talent ELOs are combined into a single **composite ELO** using configurable weights. Different composite formulations serve different use cases.

**Default batter composite (balanced, for leaderboard ranking):**

| Dimension | Weight |
|---|---|
| Contact | 0.23 |
| Power | 0.23 |
| Discipline | 0.22 |
| Speed | 0.10 |
| Clutch | 0.22 |

**Fantasy batter composite (for ESPN H2H scoring optimization):**

| Dimension | Weight |
|---|---|
| Contact | 0.30 |
| Power | 0.35 |
| Discipline | 0.25 |
| Speed | 0.10 |

**Pitcher composites by role:**

| Dimension | Starter | Reliever | Closer |
|---|---|---|---|
| Stuff | 0.25 | 0.35 | 0.35 |
| BIP Suppression | 0.20 | 0.20 | 0.25 |
| Command | 0.40 | 0.30 | 0.25 |
| Clutch | 0.15 | 0.15 | 0.15 |

The role-differentiated pitcher composites reflect real differences in what matters for each archetype: a starter needs Command above all else (pitch 6 innings without walking 5 batters), while a closer needs Stuff and BIP Suppression to dominate short, high-leverage appearances.

### 4.12 Career vs. Season ELO Blending

For players with thin current-season samples (late call-ups, early in the season, injury returnees), the system blends season ELO with career ELO:

```
blended_elo[d] = 0.67 × season_elo[d] + 0.33 × career_elo[d]
```

This blend activates automatically in `EloLookup.get_batter_elo()` when the player's PA count for a dimension falls below its reliability threshold. The career ELO represents multi-year accumulated evidence and provides a much more informative prior than starting cold at 1500.

### 4.13 Database Schema: Talent ELO Tables

```sql
-- Current talent ELO per player per dimension
CREATE TABLE talent_player_current (
    player_id    INTEGER NOT NULL,
    player_role  TEXT NOT NULL,    -- 'batter' or 'pitcher'
    talent_type  TEXT NOT NULL,    -- 'contact', 'power', 'discipline', 'speed',
                                   -- 'clutch', 'stuff', 'bip_suppression', 'command'
    season_elo   FLOAT NOT NULL DEFAULT 1500.0,
    career_elo   FLOAT NOT NULL DEFAULT 1500.0,
    event_count  INTEGER NOT NULL DEFAULT 0,
    pa_count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, talent_type, player_role)
);

-- PA-level talent ELO detail (one row per player per dimension per PA)
CREATE TABLE talent_pa_detail (
    id          BIGSERIAL PRIMARY KEY,
    pa_id       BIGINT NOT NULL REFERENCES plate_appearances(pa_id),
    player_id   INTEGER NOT NULL,
    player_role TEXT NOT NULL,
    talent_type TEXT NOT NULL,
    elo_before  FLOAT,
    elo_after   FLOAT,
    delta       FLOAT GENERATED ALWAYS AS (elo_after - elo_before) STORED,
    UNIQUE (pa_id, player_id, talent_type)
);

-- Daily OHLC per player per talent dimension
CREATE TABLE talent_daily_ohlc (
    id          BIGSERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL,
    game_date   DATE NOT NULL,
    talent_type TEXT NOT NULL,
    elo_type    TEXT NOT NULL DEFAULT 'SEASON',
    open_elo    FLOAT,
    high_elo    FLOAT,
    low_elo     FLOAT,
    close_elo   FLOAT,
    delta       FLOAT GENERATED ALWAYS AS (close_elo - open_elo) STORED,
    range       FLOAT GENERATED ALWAYS AS (high_elo - low_elo) STORED,
    total_pa    INTEGER DEFAULT 0,
    UNIQUE (player_id, game_date, talent_type, elo_type)
);
```

---

## 5. Configuration Reference

All system parameters live in `config/multi_elo_config.yaml` and `config/team_elo_config.yaml`. No magic numbers appear in source code — every tunable is referenced by name from these files.

**Key global constants:**

```yaml
# multi_elo_config.yaml
constants:
  default_elo: 1500.0
  elo_min: 500.0
  elo_max: 3000.0
  min_reliability: 0.3

# elo_config.py (core ELO constants)
INITIAL_ELO: 1500.0
MIN_ELO: 500.0
K_FACTOR: 12.0
ADJUSTMENT_SCALE: 0.1
PHYSICS_ALPHA: 0.3
PHYSICS_MOD_MIN: 0.7
PHYSICS_MOD_MAX: 1.3
LEAGUE_AVG_XWOBA: 0.315
```

---

## 6. Daily Pipeline: How ELO Is Updated

The nightly pipeline is orchestrated by `src/pipeline/daily_pipeline.py` and triggered by GitHub Actions at 8:00 AM EST every day. Here is the complete sequence:

```
1. IDEMPOTENCY CHECK
   → Skip if target_date already processed (unless force=True)

2. FETCH STATCAST
   → pybaseball.statcast(start_dt=target_date, end_dt=target_date)
   → Filter to game_type='R' (regular season only)

3. ETL: PITCH → PA
   → statcast_to_pa.py: convert to one row per PA

4. PLAYER REGISTRATION
   → detect_new_player_ids_batch(): find new IDs not in players table
   → register_new_players(): fetch names from MLB Stats API, insert

5. UPSERT PLATE APPEARANCES
   → plate_appearances table: upsert all PA records

6. LOAD ELO STATE
   → player_elo table: load all current ELO ratings

7. CORE ELO BATCH
   → EloBatch: process all PAs chronologically
   → Produces: updated player_elo, elo_pa_detail, daily_ohlc

8. UPSERT CORE ELO RESULTS
   → player_elo: upsert current ELO per player
   → elo_pa_detail: insert PA detail records
   → daily_ohlc: upsert daily OHLC

9. LOAD TALENT STATE
   → talent_player_current: load all current dimension ELOs

10. TALENT ELO BATCH
    → TalentBatch: process all PAs, 9 dimensions simultaneously
    → Handles baserunning events separately (runner_id instead of batter_id)

11. UPSERT TALENT RESULTS
    → talent_player_current: upsert all 9 dimensions per player
    → talent_pa_detail: insert PA detail records
    → talent_daily_ohlc: upsert daily OHLC per dimension

12. LOG SUMMARY
    → Players updated, PAs processed, ELO ranges
```

The full pipeline typically runs in under 5 minutes for a normal game day (~600–800 PAs).

---

## 7. Model Calibration and Tuning

### K-Factor Rationale

The core ELO K-factor of 12.0 (base, pre-event-type modulation) was selected via sensitivity analysis targeting **stable daily volatility** — the goal was that a strong day's performance moves a player by roughly 10–20 ELO points (not 50+, which would make ratings too noisy, and not <2, which would make them too stagnant).

### Talent Dimension K-Factors and Scales

Dimension-specific parameters were tuned manually with the following principles:

- **K × Scale** = maximum possible single-event ELO movement at full reliability for an extreme event weight (1.00).
- Power K×Scale = 14.4 × 10.0 = 144 (a home run can move Power by up to 144 × reliability points — aggressive, because HRs are rare and unambiguous).
- Contact K×Scale = 12.0 × 5.0 = 60 (moderate, because contact events are frequent and noisier).
- Speed K×Scale = 36.0 × 4.0 = 144 (same ceiling as Power, because stolen base attempts are rare and decisive).

### ZSCORE_DIVISOR Calibration

The matchup prediction engine (see `matchup.md`) converts talent ELO z-scores into PA outcome probabilities using divisors that were calibrated via **log-loss minimization** in `notebooks/calibrate_divisors.ipynb`:

1. Load all historical PAs with known outcomes (2025 season).
2. Compute batter/pitcher z-scores for each PA.
3. Run the 3-stage prediction model with varying divisor values in a grid search.
4. Select divisors minimizing the holdout cross-entropy loss.

Final values: `stage1_bb=3.13, stage1_k=8.42, stage2=20.0, stage3=16.4, stage1_hbp=7.0`.

### Expected Divisors per Dimension

The ELO expected-score formula uses a divisor (analogous to the 400 in standard ELO) that controls how much rating difference is needed to shift win probability. Larger divisors mean ELO differences matter less per point.

These divisors were set to match the **observed variance of each dimension's ELO distribution** — ensuring that a 1-standard-deviation difference in dimension ELO corresponds to a meaningful but not extreme shift in expected outcome probability. They are calibrated from the observed population after a full season of rating accumulation.

---

## 8. Known Limitations and Future Work

| Limitation | Description | Potential Fix |
|---|---|---|
| **Leverage Index** | Clutch dimension uses RISP/outs as a proxy for LI rather than true LI | Integrate FanGraphs/Baseball Reference LI via API |
| **Pre-season Speed seeding** | Speed ELO requires SB/CS data; new players start at 1500 regardless of known speed profile | Pre-seed from Statcast sprint speed data |
| **Career ELO for cross-year continuity** | Career ELO currently resets with same formula as season ELO; multi-year historical backfill is partial | Full historical Statcast backfill (2017–present) |
| **Two-way player handling** | Shohei Ohtani and other two-way players currently get separate batter/pitcher ratings; composite display requires manual role selection | Automated role detection + separate composite tracks |
| **Form adjustment (ME-1)** | 7-day OHLC momentum dampening is computed but not yet integrated into matchup projections | Wire `daily_ohlc` momentum signal into `EloLookup` |
| **Team ELO in projections (ME-4)** | Team ELO opponent weight is calculated but not applied to matchup predictions | Integrate team difficulty scaling into pitcher ELO lookup |
| **Park-neutral Speed** | Baserunning events don't apply park factors (turf, grass) | Research stadium-specific SB success rate adjustments |

---

*This document was written to serve as a definitive reference for the ELO systems powering the Fantasy Matchup Predictor. For the prediction engine that consumes these ratings, see `docs/matchup.md`.*
