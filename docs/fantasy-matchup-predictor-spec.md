# Fantasy Matchup Predictor — Functional Specification

**Status**: Complete (all 4 phases implemented)
**Date**: 2026-04-16
**Based on**: mlb-elo-demo-2025 ELO engine + matchup predictor

---

## 1. Overview

A standalone Python + React web app that:
1. Reads the user's ESPN fantasy roster from a local `roster.md` file
2. Pulls the weekly MLB schedule (probable pitchers per game) via MLB Stats API
3. Fetches supplementary Fangraphs context stats via pybaseball
4. Calculates team ELO ratings (FiveThirtyEight-style) to identify hot/cold opponents
5. Runs the existing 3-stage ELO matchup predictor for each batter-vs-pitcher pairing
6. Outputs projected ESPN fantasy points per player per game, with a weekly summary
7. Generates a PDF report for the week

---

## 2. ESPN Scoring System

```yaml
batter:
  TB:  +1   # 1B=1, 2B=2, 3B=3, HR=4
  R:   +1
  RBI: +1
  BB:  +1
  SB:  +1
  SO:  -1
  E:   -3   # Errors

pitcher:
  IP:  +3   # per full inning pitched
  K:   +1
  W:   +5
  SV:  +5
  H:   -1
  ER:  -1
  HR:  -1
  BB:  -1
  HB:  +1   # Hit batters (positive — incentivizes aggressive pitching)
  L:   -5
  BS:  -5   # Blown saves
  B:   -10  # Balks
  PKO: +2   # Pickoffs
  CG:  +3   # Complete games
  SHO: +5   # Shutouts
  NH:  +10  # No hitters
  PG:  +11  # Perfect games
```

**Format**: H2H Points league

**ESPN Lineup Slots**: C, 1B, 2B, SS, 3B, MI (2B/SS flex), CI (1B/3B flex), OF×5, UTIL (any) + 9 pitchers (mix of SP/RP).
Players on the bench do not accrue stats. Multi-position eligible players (e.g., 1B/OF) can fill any of their eligible slots — the roster parser tracks all eligible positions for lineup flexibility analysis.

---

## 3. Data Sources

### 3.1 Player ELO Ratings — Supabase (new instance)
- Fresh Supabase setup required
- Tables needed: `talent_player_current`, `players`
- Load using existing Python ETL pipeline (`src/etl/`, `src/engine/`)
- One-time bulk load of 2025 Statcast data; incremental updates as 2026 season progresses

### 3.2 Team ELO Ratings — Supabase (new table, required for v1)
- FiveThirtyEight-style team ELO system built alongside player ELO
- See Section 5.8 for full design
- Stored in new `team_elo` Supabase table
- Provides "hot/cold team" context for each opponent your players face

### 3.3 User Roster — `roster.md`
Updated by user each week. Format:

```markdown
# My Fantasy Roster

## Batters
- Vladimir Guerrero Jr. (1B/DH) — TOR
- Yordan Alvarez (OF/DH) — HOU
...

## Pitchers
- Corbin Burnes (SP) — ARI
- Emmanuel Clase (RP) — CLE
...
```

- Multi-position eligibility listed in parentheses (e.g., `1B/DH`)
- Roster parser tracks all eligible positions for each batter
- Positions are used for **lineup slot flexibility display only** — they do not change the matchup prediction math

### 3.4 Weekly MLB Schedule — MLB Stats API (free, no key)
- **Why not pybaseball**: pybaseball's `schedule_and_record()` does not return probable pitchers for future games — it's results-only. MLB Stats API is required for real-time probable pitchers.
- Endpoint: `https://statsapi.mlb.com/api/v1/schedule`
- Query by team + date range (Mon–Sun of current week)
- Returns: game dates, home/away teams, probable pitcher IDs
- Fallback: if probable pitcher is "TBD" (common early in week), fall back to team's rotation leader by IP

### 3.5 Supplementary Fangraphs Stats — pybaseball
Used for **display context alongside ELO** — does not affect matchup prediction math.

**Batter stats** via `pybaseball.batting_stats(season)`:
- wRC+ (park/league-adjusted weighted runs created)
- wOBA
- Clutch

**Pitcher stats** via `pybaseball.pitching_stats(season)`:
- ERA−
- xFIP−
- FIP−

**Season rates** (for fantasy point estimation of R, RBI, SB, W, IP, SV):
- `pybaseball.batting_stats_range(start_dt, end_dt)` — batter R/G, RBI/G, SB/G rates
- `pybaseball.pitching_stats_range(start_dt, end_dt)` — pitcher IP/start, W rate, SV rate

---

## 4. System Architecture

```
roster.md
    │
    ▼
[Roster Parser]
    │ batters: [{name, team, positions[]}]
    │ pitchers: [{name, team, type}]
    ▼
[MLB Schedule Fetcher]              ←── MLB Stats API
    │ weekly games per team
    ▼
[Opponent Resolver]
    │ batters → probable opposing pitchers (per game day)
    │ pitchers → opposing team's top 9 batters (by PA count)
    ▼
[Data Enrichment — parallel]
    ├── [ELO Lookup]                ←── Supabase talent_player_current
    │       BatterTalentElo, PitcherTalentElo (9D)
    ├── [Team ELO Lookup]           ←── Supabase team_elo
    │       Opponent team current ELO + recent trend
    └── [Fangraphs Lookup]          ←── pybaseball
            wRC+/wOBA/Clutch (batters), ERA-/xFIP- (pitchers)
            Season rate stats for fantasy point estimation
    ▼
[Matchup Predictor]                 ←── Port of matchupPredictor.ts to Python
    │ P(BB), P(K), P(1B), P(2B), P(3B), P(HR), P(OUT) per PA
    ▼
[Fantasy Points Calculator]
    │ ELO-derived: TB, BB, SO, H_allowed, BB_allowed, K_allowed
    │ Rate-based: R, RBI, SB, IP, ER, W/L/SV/HD
    ▼
[Report Generator]
    │ Weekly grid (batter view + pitcher view)
    │ Single matchup detail
    ├── Web UI (React)
    └── PDF export
```

---

## 5. Core Components

### 5.1 Roster Parser (`src/fantasy/roster_parser.py`)
- Reads `roster.md`
- Returns:
  ```python
  {
    "batters": [{"name": str, "team": str, "positions": ["1B", "DH"]}],
    "pitchers": [{"name": str, "team": str, "type": "SP"|"RP"}]
  }
  ```
- Fuzzy-matches player names to `players` table in Supabase (handles typos/nicknames)
- Positions stored for slot-flexibility display only

### 5.2 Schedule Fetcher (`src/fantasy/schedule_fetcher.py`)
- Calls `https://statsapi.mlb.com/api/v1/schedule` for Mon–Sun of target week
- Input: list of MLB team codes
- Output: `{ team: [{ date, opponent_team, probable_pitcher_id, home_away }] }`
- Fallback: TBD pitcher → query team pitching stats for likely starter

### 5.3 Opponent Resolver (`src/fantasy/opponent_resolver.py`)
- **For batters**: each game day → probable opposing pitcher
- **For pitchers**: each start → opponent team's top 9 batters (ranked by 2025 PA count from `plate_appearances` table)
- Output: list of `(batter_id, pitcher_id, game_date)` tuples for the week

### 5.4 ELO Lookup (`src/fantasy/elo_lookup.py`)
- Queries `talent_player_current` for batter dimensions: contact, power, discipline
- Queries `talent_player_current` for pitcher dimensions: stuff, bip_suppression, command
- Queries `team_elo` for opponent team current ELO + 10-game rolling trend
- In-memory cache to avoid repeat Supabase calls per session

### 5.5 Fangraphs Enricher (`src/fantasy/fangraphs_enricher.py`)
- `pybaseball.batting_stats(2025)` → wRC+, wOBA, Clutch per batter
- `pybaseball.pitching_stats(2025)` → ERA−, xFIP−, FIP− per pitcher
- `pybaseball.batting_stats_range(...)` → R/G, RBI/G, SB/G rates
- `pybaseball.pitching_stats_range(...)` → IP/start, W rate, SV/HD rate
- Output: enrichment dict keyed by player name; merged into player objects

### 5.6 Speed ELO (`src/engine/` + `scripts/seed_speed_elo_fg.py`)

A dedicated ELO dimension for stolen base talent, separate from the main multi-dimensional talent ELO.

- **Seeded from**: Fangraphs sprint speed (ft/s) via `seed_speed_elo_fg.py`
- **Mean**: 1500, **Std**: ~50 — same distribution as other ELO dimensions
- **Used in**: `estimate_batter_points()` — scales stolen base rate via `speed_z = (speed_elo - 1500) / 50`
- **Also drives**: Stage 3 triple split in `matchup_predictor.py` (faster batters have higher P(3B))
- **Stored in**: `talent_player_current` table, `speed` dimension column

### 5.7 Matchup Predictor (`src/fantasy/matchup_predictor.py`)
- Port of `frontend/src/lib/matchupPredictor.ts` to Python
- Same 3-stage decision tree (softmax → BIP → XBH split)
- Same ELO distribution constants from `scripts/compute_matchup_constants.py`
- Input: `BatterTalentElo`, `PitcherTalentElo`
- Output per PA: `{ bb, k, out, single, double, triple, hr, xwoba }`
- Batch-friendly: accepts list of `(batter_elo, pitcher_elo)` tuples

### 5.8 Fantasy Points Calculator (`src/fantasy/fantasy_calculator.py`)

**Directly estimated per PA from matchup predictor:**

| Stat | Formula |
|------|---------|
| TB (batter) | `(1×P(1B) + 2×P(2B) + 3×P(3B) + 4×P(HR)) × PAs` |
| BB (batter) | `P(BB) × PAs` |
| SO (batter) | `P(K) × PAs` |
| H allowed (pitcher) | `P(hit) × batters_faced` |
| BB allowed (pitcher) | `P(BB) × batters_faced` |
| K (pitcher) | `P(K) × batters_faced` |
| ER (pitcher) | `(hits + BB + HBP) × 0.30 × batters_faced` |

**Estimated from calibration config + ELO:**

| Stat | Method |
|------|--------|
| R | `TB × r_per_tb (config) + speed_z × 0.015` |
| RBI | `TB × rbi_per_tb (config)` |
| SB | `(1B + BB + HBP) × speed_factor × pitcher_sb_factor × base_rate` |
| IP | `Fangraphs IP/GS (SP); season_ip/season_g (RP)` |
| W/L | `base rate adjusted by pitcher ELO vs opponent team ELO` |
| SV/HLD | `Fangraphs historical sv_per_app and hld_per_app` |
| BS | `SV opportunities × 15% blown save rate` |

**Expected PAs per game:** flat `3.9 PA/game` (batting order position not tracked)

**Output:** all point values rounded to nearest whole number

### 5.9 Team ELO Engine (`src/engine/team_elo_engine.py`)

FiveThirtyEight-style team ELO system. Runs in parallel with player ELO.

**Algorithm**:
- Each team starts at 1500 ELO
- After each game: winner gains points, loser loses equal points (zero-sum)
- **K-factor**: 4 base (lower than player ELO, team form is slower-moving)
- **Home field**: +24 ELO points for expected score calculation
- **Margin of victory multiplier**: `log(run_diff + 1) × adjustment` (diminishing returns, prevents blowout inflation)
- **Season reset**: regress 1/3 of the way back to 1500 each new season (carry prior form, not full reset)

**Data source**: Game results from `plate_appearances` table (already loaded — deduce final score from `bat_score`/`fld_score` at final PA of each game)

**Output table** (`team_elo`):
```sql
team_code     TEXT
game_date     DATE
elo_before    FLOAT
elo_after     FLOAT
opponent_code TEXT
result        TEXT  -- W/L
run_diff      INT
```

**UI use**: Show opponent team ELO + trend badge (🔥 hot / 🧊 cold) on batter and pitcher matchup views.

### 5.10 Report Generator (`src/fantasy/report.py`)
- Per batter: game-by-game grid (opponent pitcher, matchup ELO breakdown, projected pts)
- Per pitcher: projected starts, opponent lineup ELO average, projected pts
- Team ELO badge for each opponent
- Fangraphs stat sidebar (wRC+, ERA−, etc.)
- **Output formats**:
  - Terminal table (CLI use)
  - HTML (for web UI)
  - **PDF** (via `weasyprint` or `reportlab` — weekly printable report)

---

## 6. Web UI

**Stack**: React 19 + TypeScript + Vite + Tailwind (same as existing frontend)

### `/` — Weekly Dashboard
- Roster summary (loaded from `roster.md`)
- Week selector (defaults to current week)
- Team ELO trend for each opponent team this week
- Total projected points summary card

### `/batters` — Batter Matchup Grid
- Table: Batter | Positions | Mon | Tue | Wed | Thu | Fri | Sat | Sun | Total Pts
- Each cell: opposing pitcher name + projected pts
- Color coding: green (favorable ELO matchup) / red (unfavorable)
- Click cell → matchup detail modal

### `/pitchers` — Pitcher Matchup View
- Table: Pitcher | Start date(s) | Opponent | Team ELO | Proj IP | Proj K | Proj Pts
- Click row → opponent lineup ELO breakdown

### `/matchup/:batterId/:pitcherId` — Single Matchup Detail
- Reuse existing `MatchupBar`, `StageResults`, `FinalPrediction` components
- Add `FantasyPointsPanel` below (ESPN pts breakdown)
- Add Fangraphs stat sidebar (wRC+, wOBA, ERA−, xFIP−)
- Add opponent team ELO badge

### `/export` — PDF Export
- Trigger weekly PDF generation
- Download link for `week_YYYY-MM-DD_report.pdf`

---

## 7. Project Structure

```
fantasy-matchup/
├── roster.md                              # User updates weekly
├── .env                                   # SUPABASE_URL, SUPABASE_KEY
├── src/
│   ├── engine/
│   │   └── team_elo_engine.py             # NEW: FiveThirtyEight-style team ELO
│   └── fantasy/
│       ├── roster_parser.py
│       ├── schedule_fetcher.py            # MLB Stats API
│       ├── opponent_resolver.py
│       ├── elo_lookup.py                  # Player + team ELO from Supabase
│       ├── fangraphs_enricher.py          # pybaseball wrapper
│       ├── matchup_predictor.py           # Port of matchupPredictor.ts
│       ├── fantasy_calculator.py
│       └── report.py                      # Terminal + HTML + PDF
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── WeeklyDashboard.tsx
│       │   ├── BatterMatchups.tsx
│       │   ├── PitcherMatchups.tsx
│       │   └── ExportPage.tsx
│       └── components/
│           ├── matchup/                   # Reuse all existing components
│           └── fantasy/
│               ├── FantasyPointsPanel.tsx
│               ├── WeeklyGrid.tsx
│               ├── TeamEloBadge.tsx
│               └── FanGraphsSidebar.tsx
├── .github/
│   └── workflows/
│       └── daily_update.yml               # GitHub Actions: daily 8am EST automation
├── .cache/                                # Fangraphs daily cache (gitignored)
├── logs/                                  # Daily run logs (gitignored)
└── scripts/
    ├── run_daily.py                       # Orchestrator: runs all 5 daily pipeline steps
    ├── run_weekly.py                      # CLI: python run_weekly.py (manual use)
    └── backfill_team_elo.py               # One-time: compute team ELO from 2025 data
```

---

## 8. New Dependencies

```
pybaseball      # Fangraphs stats + season rates
reportlab        # PDF generation
rapidfuzz       # Fuzzy player name matching
```

---

## 9. Setup Steps (Fresh Supabase)

1. Create Supabase project → copy URL + anon key to `.env`
2. Run migrations: `scripts/migrations/001_create_tables.sql` through `005_...`
3. Add team ELO migration: `scripts/migrations/006_team_elo.sql` (new)
4. Load Statcast 2025 parquet data via ETL pipeline
5. Run ELO engine: `python -m scripts.daily_elo --range 2025-03-27 2025-09-30`
6. Run talent ELO: `python -m src.engine.talent_batch`
7. Run team ELO backfill: `python scripts/backfill_team_elo.py --season 2025`
8. Compute matchup constants: `python scripts/compute_matchup_constants.py`
9. Start frontend: `cd frontend && npm install && npm run dev`
10. Push to private GitHub repo; add `SUPABASE_URL` + `SUPABASE_KEY` to repo Secrets
11. Create `.github/workflows/daily_update.yml` → automation runs daily at 8am EST

---

## 10. Open Questions / Future Work

| Item | Status |
|------|--------|
| ELO engine revision (add Fangraphs stats as ELO inputs) | Deferred — separate task |
| ESPN API import for automatic roster sync | Deferred — v2 |
| Opponent's fantasy roster (not real MLB opponents) | Deferred — v2 |
| Live probable pitcher updates (intraday refresh) | Deferred — v2 |

---

## 11. Limitations & Notes

- **Probable pitchers**: MLB Stats API returns them ~24h before game time. Early-week games show TBD — fallback to team rotation leader.
- **pybaseball rate limits**: Baseball Reference has a 10 req/min limit. Data is cached locally after first fetch.
- **Relief pitcher W/SV/HD**: Model uses historical rates, not game-by-game prediction.
- **R and RBI**: Context-dependent (teammates on base). Season rate is a reasonable proxy.
- **2026 season**: 2025 ELO data is the prior. Update incrementally as 2026 games are played.
- **Team ELO accuracy**: Small sample early in season — treat with lower confidence before ~30 games.

---

## 12. Reusable Code from Existing Project

| File | Reuse |
|------|-------|
| `frontend/src/lib/matchupPredictor.ts` | Port to `src/fantasy/matchup_predictor.py` |
| `frontend/src/components/matchup/` | All 4 components reused as-is |
| `frontend/src/api/matchup.ts` | Reuse ELO query patterns |
| `frontend/src/lib/supabase.ts` | Direct copy |
| `src/engine/multi_elo_engine.py` | No change needed |
| `src/etl/` | No change needed |
| `config/multi_elo_config.yaml` | No change needed |
| `scripts/compute_matchup_constants.py` | No change needed |

---

## 13. Daily Automation (GitHub Actions)

### Why Daily
- Probable pitchers post to MLB API ~24h before first pitch — stale data = wrong matchup predictions
- Player and team ELO must update after each game day's results
- Fangraphs season rates drift as the season progresses
- Day-by-day lineup decisions benefit from projections refreshed each morning

### Daily Pipeline (runs at 8:00 AM EST via GitHub Actions)

| Step | Script | Action |
|------|--------|--------|
| 1 | `scripts/daily_elo.py --date yesterday` | Update player ELO from yesterday's game PAs |
| 2 | `scripts/backfill_team_elo.py --date yesterday` | Update team ELO from yesterday's results |
| 3 | `src/fantasy/schedule_fetcher.py --week current` | Refresh probable pitchers for remaining games this week |
| 4 | `src/fantasy/fangraphs_enricher.py --refresh` | Pull latest Fangraphs season rates (cached daily) |
| 5 | `scripts/run_weekly.py --regenerate` | Recompute all matchup predictions + regenerate HTML/PDF |

**Entry point**: `scripts/run_daily.py` — orchestrates all 5 steps, writes `logs/daily_YYYY-MM-DD.log`.

### Idempotency Requirements
All steps must be safe to re-run without creating duplicates:
- Supabase ELO tables: upsert on `(player_id, game_date)` and `(team_code, game_date)`
- Schedule data: overwrite, not append
- Fangraphs: cache to `.cache/fangraphs_YYYY-MM-DD.json`; skip fetch if cache exists for today

### GitHub Actions Workflow

```yaml
# .github/workflows/daily_update.yml
on:
  schedule:
    - cron: '0 13 * * *'  # 8:00 AM EST = 13:00 UTC
  workflow_dispatch:         # Manual trigger as fallback

jobs:
  daily-update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/run_daily.py
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

- Runs cloud-hosted even if local machine is off
- Free tier: 2,000 min/month — this job runs ~5 min/day (~150 min/month)
- Built-in email notification on failure
- `workflow_dispatch` allows manual re-run from GitHub UI

### Setup Steps
1. Push project to a private GitHub repo
2. Add `SUPABASE_URL` and `SUPABASE_KEY` to repo Settings → Secrets and variables → Actions
3. Create `.github/workflows/daily_update.yml` with the workflow above
4. GitHub automatically emails on workflow failure

### Logging & Alerting

| Method | How |
|--------|-----|
| Log file | `logs/daily_YYYY-MM-DD.log` written by `run_daily.py` |
| Failure alert | GitHub Actions built-in — email sent to repo owner automatically |
| Manual trigger | Use "Run workflow" button in GitHub Actions tab |

### New Files Added

| File | Purpose |
|------|---------|
| `scripts/run_daily.py` | Orchestrator — runs all 5 pipeline steps in sequence |
| `.github/workflows/daily_update.yml` | GitHub Actions schedule definition |
| `.cache/` | Local cache for Fangraphs data (gitignored) |
| `logs/` | Daily run logs (gitignored) |
