# Fantasy Projection Model — How Points Are Calculated

This document explains the full calculation pipeline behind the weekly fantasy
projections, including what data is actually used, what is approximated, and
what is currently not implemented.

---

## Pipeline Overview

```
Roster text
    ↓
roster_parser.py          — parse player names, teams, slots
    ↓
schedule_fetcher.py       — fetch MLB schedule + probable pitchers from statsapi.mlb.com
    ↓
opponent_resolver.py      — match each roster player to their weekly games/opponents
    ↓
elo_lookup.py             — fetch talent ELO from talent_player_current (Supabase)
    ↓
matchup_predictor.py      — 3-stage decision tree → PA outcome probabilities
    ↓
fantasy_calculator.py     — probabilities × ESPN scoring weights → projected points
```

---

## Stage 1 — Schedule & Opponent Resolution

### Batters
Every game their team plays during the week is included. Each game is paired with
the **opposing team's probable pitcher** (name + player ID from the MLB Stats API).

### Pitchers
**Only games where they are listed as the probable pitcher** in the MLB Stats API
are included. This means:

- **Starters (SP):** Get projections only for their scheduled starts (usually 1–2 per week).
- **Relievers (RP):** MLB's Stats API almost never lists a reliever as a "probable pitcher."
  As a result, **RPs currently receive zero projected points** — their slot contributes
  nothing to the weekly total. This is a known gap (see Known Limitations).

---

## Stage 2 — Talent ELO Lookup

Talent ELO values are fetched from the `talent_player_current` table in Supabase.

### Pitcher dimensions (3):
| Dimension | What it measures |
|-----------|-----------------|
| `stuff` | Ability to generate swings and misses / strikeouts |
| `bip_suppression` | Ability to suppress hits on balls in play |
| `command` | Walk avoidance |

### Batter dimensions (3):
| Dimension | What it measures |
|-----------|-----------------|
| `contact` | Ability to make contact on balls in play |
| `power` | Extra-base hit rate |
| `discipline` | Walk drawing / strikeout avoidance |

### ⚠️ Current Limitation — Batter ELO Not Used

**Batter talent ELO is not actually applied in projections.** The code calls
`elo_lookup.get_batter_elo(0)` (player ID = 0), which always returns the league
default (1500 / 1500 / 1500) for every batter. This means **all batters on the same
team facing the same pitcher receive identical projected points** — their individual
talent is not factored in.

Likewise, **pitcher ELO is not applied to their own start projection.** The pitcher's
points are computed using default ELO (1500) regardless of their actual talent.

The **only ELO value that actually affects projections** today is the **opposing
pitcher's talent**, which determines how hard that pitcher is to hit against —
affecting batter point projections.

> Root cause: Roster parsing currently does not resolve player names to numeric
> player IDs for batters or for the starting pitcher themselves. Implementing
> this lookup (fuzzy name → player ID → talent ELO) would make projections
> player-specific.

---

## Stage 3 — Matchup Prediction (3-Stage Decision Tree)

Each plate appearance (batter vs. pitcher) is modeled as a 3-stage decision tree
using ELO z-scores against 2025 MLB distributions.

### Stage 1 — Softmax: BB / K / Ball In Play
Determines the probability the PA ends in a walk, strikeout, or ball in play.

```
z_disc_cmd  = z(batter.discipline) − z(pitcher.command)
z_stuff_contact = z(pitcher.stuff) − z(batter.contact)

P(BB), P(K), P(BIP) via 3-way softmax
```

High `z_disc_cmd` → more walks. High `z_stuff_contact` → more strikeouts.

### Stage 2 — Hit vs. Out (given ball in play)
```
z_contact_bip = z(batter.contact) − z(pitcher.bip_suppression)

P(Hit | BIP) via logistic, centered on MLB average hit rate (32.1%)
```

### Stage 3 — XBH vs. Single (given hit)
```
z_power = z(batter.power)   [pitcher has no effect on this stage]

P(XBH | Hit) via logistic, centered on 34.9%
XBH split: 2B = 55.2%, 3B = 4.5%, HR = 40.3%
```

### League averages used as anchors:
| Event | Rate |
|-------|------|
| Walk (BB) | 9.49% |
| Strikeout (K) | 22.18% |
| Ball in play (BIP) | 68.34% |
| Hit rate on BIP | 32.06% |
| XBH rate on hit | 34.93% |

### Expected wOBA
```
wOBA = 0.69×P(BB) + 0.88×P(1B) + 1.24×P(2B) + 1.56×P(3B) + 2.00×P(HR)
```

---

## Stage 4 — Fantasy Points Calculation

### Batters

`estimate_batter_points(probs, scoring, pas=3.9)`

Each batter is assumed to have **3.9 PA per game** (MLB average). Points are
calculated per PA and scaled up.

| Stat | Calculation | ESPN Points |
|------|-------------|-------------|
| Total Bases | P(1B)×1 + P(2B)×2 + P(3B)×3 + P(HR)×4 | ×1 |
| Runs | 40% of expected TB | ×1 |
| RBI | 45% of expected TB | ×1 |
| Walks | P(BB) | ×1 |
| Strikeouts | P(K) | ×−1 |
| Stolen bases | 2% of (P(1B) + P(BB)) | ×1 |

> Runs and RBI are rough proxies (MLB seasonal correlations), not derived from
> lineup context. Stolen bases use a flat 2% on-base rate assumption.

### Pitchers (Starters only)

`estimate_pitcher_points(probs, scoring, innings=6.0)`

Every pitcher start assumes a **flat 6.0 innings pitched** regardless of pitcher
type or skill level. Batters faced = 6.0 × 4.3 = **25.8 BF**.

| Stat | Calculation | ESPN Points |
|------|-------------|-------------|
| Innings Pitched | 6.0 (fixed) | ×3 |
| Strikeouts | P(K) × 25.8 | ×1 |
| Hits allowed | P(hit) × 25.8 | ×−1 |
| Earned Runs | 30% of (hits + BB) | ×−2 |
| Walks | P(BB) × 25.8 | ×−1 |

**Not currently calculated:** Wins (W +2), Saves (SV +5), Holds (HD +2),
Losses (L −2) — these appear in `espn_scoring.yaml` but are not included in
`estimate_pitcher_points`.

---

## ESPN Scoring Reference

From `config/espn_scoring.yaml`:

```yaml
batter:
  TB:  +1   # Total bases (1B=1, 2B=2, 3B=3, HR=4)
  R:   +1   # Runs
  RBI: +1   # RBIs
  BB:  +1   # Walks
  SB:  +1   # Stolen bases
  SO:  -1   # Strikeouts

pitcher:
  IP:  +3   # Per inning pitched
  K:   +1   # Strikeouts
  W:   +2   # Win  ← not projected
  SV:  +5   # Save ← not projected
  HD:  +2   # Hold ← not projected
  H:   -1   # Hits allowed
  ER:  -2   # Earned runs
  BB:  -1   # Walks allowed
  L:   -2   # Loss ← not projected
```

---

## Known Limitations & Improvement Roadmap

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 1 | Batter ELO defaults to 1500 for all players | All teammates project identically | Resolve roster names → player IDs → talent ELO |
| 2 | Pitcher own-ELO defaults to 1500 | Pitcher start quality not reflected | Same as above |
| 3 | RPs get zero projection | Saves/holds/holds never appear | Use FanGraphs closer rankings or a BF-based RP model with flat 1 IP assumption |
| 4 | IP hardcoded at 6.0 for all starters | Aces and back-of-rotation guys treated equally | Use pitcher talent ELO to scale innings (e.g. elite stuff → 6.5 IP, replacement → 5.5 IP) |
| 5 | W/SV/HD/L not projected | Points underestimated for closers/high-win pitchers | Approximate W% from team win probability; SV from closer role + opp wOBA |
| 6 | Runs/RBI are TB proxies, not lineup-aware | Doesn't account for lineup position or team offense | Add lineup context from Fangraphs team OPS or team ELO as a multiplier |
| 7 | SB rate is flat 2% | Ignores player speed profile | Add SB talent dimension to batter ELO |

---

## Data Sources

| Data | Source | Freshness |
|------|--------|-----------|
| Talent ELO | `talent_player_current` (Supabase) | Updated daily by GitHub Actions |
| Schedule + probable pitchers | `statsapi.mlb.com` | Live at projection time |
| Fangraphs batting/pitching stats | `pybaseball` | Daily parquet cache |
| ESPN scoring rules | `config/espn_scoring.yaml` | Static — edit manually if your league settings differ |
