# Fantasy Matchup Predictor

A fantasy baseball tool that combines MLB ELO ratings with ESPN H2H points scoring to project weekly matchups. Built on FiveThirtyEight-style ELO systems for both individual players and teams, with a 9-dimensional talent model tracking power, discipline, speed, contact, and pitching skills.

## What It Does

- **Player ELO** — zero-sum ratings for every MLB batter and pitcher, updated per plate appearance
- **9D Talent ELO** — separate ELO tracks for contact, power, discipline, speed, clutch (batters) and stuff, command, BIP suppression, clutch (pitchers); full OHLC history available per dimension
- **Team ELO** — FiveThirtyEight-style team ratings with home-field advantage, margin-of-victory scaling, and season regression
- **Fantasy Projections** — combine ELO matchup predictions with ESPN scoring rules to project weekly fantasy points
- **PDF Reports** — downloadable weekly projection reports with batter/pitcher breakdowns and team ELO rankings
- **Daily Automation** — GitHub Actions pipeline updates ELO, schedule, and Fangraphs data daily at 8am EST

## Current Status

**All phases complete.** Player ELO, talent ELO (including Speed ELO from MLB Stats API), team ELO, fantasy backend, fantasy frontend, PDF export, and daily automation are fully operational.

| Metric | Value |
|--------|-------|
| Plate appearances | 183,092+ (2025 full season + 2026 active) |
| Date range | 2025-03-27 → present (2026 season live) |
| Players tracked | 1,469+ |
| Teams tracked | 30 |
| Backend tests | 112 passing |
| Fantasy modules | 8 (roster, schedule, ELO lookup, matchup predictor, calculator, projections, Fangraphs, PDF) |
| API endpoints | 28 across 5 routers |

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, Supabase (PostgreSQL) |
| Frontend | React 19, Vite, Tailwind CSS v4, TanStack Query |
| Data | pybaseball (Statcast/Fangraphs), MLB Stats API |
| ELO Engine | Custom Python — zero-sum with park factors, RE24 baselines |
| PDF | reportlab |
| CI/CD | GitHub Actions (daily cron) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Supabase project (free tier works)

### Setup

```bash
# Clone
git clone https://github.com/boerface16/Fantasy_ELO_Tool.git
cd Fantasy_ELO_Tool

# Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your Supabase credentials:
#   SUPABASE_URL=https://your-project.supabase.co
#   SUPABASE_KEY=your-anon-key
#   DATABASE_URL=postgresql://user:pass@host:5432/postgres

# Apply database migrations (run in Supabase SQL Editor)
# scripts/migrations/001_create_tables.sql through 006_team_elo.sql

# Load 2025 season data (~5-15 minutes)
python -m scripts.bulk_load --end-date 2025-09-28 --fresh

# Load 2026 season data (incremental from opening day)
python -m scripts.bulk_load --start-date 2026-03-18

# Backfill team ELO from scratch
python -m scripts.backfill_team_elo --fresh

# Start the API
uvicorn src.api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173, proxies /api → localhost:8000
```

### Daily Updates

```bash
# Run the full daily pipeline (player ELO, team ELO, Fangraphs, schedule)
python -m scripts.run_daily

# Or update a specific date
python -m scripts.run_daily --date 2026-04-01

# Full recompute for player ELO (after data corrections)
python -m scripts.bulk_load --fresh

# Full recompute for team ELO
python -m scripts.backfill_team_elo --fresh
```

## Project Structure

```
├── config/                  # YAML configs (ELO params, ESPN scoring)
├── data/                    # Static data (park factors, RE24 baselines)
├── src/
│   ├── engine/              # ELO engines (player, talent, team)
│   ├── etl/                 # Statcast → plate appearances pipeline
│   ├── pipeline/            # Daily update orchestration
│   ├── fantasy/             # Fantasy modules
│   │   ├── roster_parser.py       # Parse ESPN roster text, fuzzy-match names
│   │   ├── schedule_fetcher.py    # MLB Stats API for probable pitchers
│   │   ├── opponent_resolver.py   # Roster × schedule → matchup tuples
│   │   ├── elo_lookup.py          # Batch Supabase queries, in-memory cache
│   │   ├── matchup_predictor.py   # 3-stage PA prediction (Python port of TS)
│   │   ├── fantasy_calculator.py  # Probabilities → ESPN fantasy points
│   │   ├── weekly_projection.py   # Orchestrator combining all modules
│   │   ├── fangraphs_enricher.py  # pybaseball wrapper with daily cache
│   │   └── report.py             # reportlab PDF generation
│   └── api/                 # FastAPI backend
│       └── routers/         # elo, talent, matchup, fantasy, export
├── scripts/
│   ├── bulk_load.py              # Fast data loader (psycopg2, ~90s)
│   ├── backfill_team_elo.py      # Compute team ELO from game results
│   ├── run_daily.py              # Daily pipeline orchestrator (5 steps)
│   ├── run_weekly.py             # Weekly Fangraphs cache refresh
│   ├── seed_speed_elo_fg.py      # Seed Speed ELO from MLB Stats API SB/CS data
│   └── migrations/               # SQL migrations (001-008)
├── frontend/                # React 19 + Vite + Tailwind
│   └── src/
│       ├── pages/           # Dashboard, Fantasy, Batters, Pitchers, Export, etc.
│       └── components/
│           ├── matchup/     # Matchup visualization components
│           └── fantasy/     # Fantasy-specific components (7 total)
├── .github/workflows/       # GitHub Actions daily automation
└── tests/                   # pytest test suite (112 tests)
```

## API Endpoints

### Player ELO (`/api/elo`)
- `GET /leaderboard` — ELO rankings by position (batter / pitcher / batter-fantasy / pitcher-fantasy)
- `GET /players/{id}` — player detail + OHLC chart data
- `GET /players/{id}/games` — last N games with ELO delta and fantasy points
- `GET /hot-players` / `cold-players` — daily ELO streakers
- `GET /hot-fantasy` / `cold-fantasy` — daily fantasy point leaders/losers (by role)
- `GET /fantasy-leaderboard` — 2026 season cumulative fantasy points (via Supabase RPC)
- `GET /search?q=` — fuzzy player search
- `GET /league-summary` — league-wide ELO stats
- `GET /latest-date` / `season-meta` — date/season info

### Talent ELO (`/api/talent`)
- `GET /leaderboard` — 9D talent rankings
- `GET /players/{id}/radar` — all talent dimensions for a player (current ELO + rank)
- `GET /players/{id}/ohlc` — talent dimension ELO history (candlestick data, by talent_type)

### Matchup (`/api/matchup`)
- `GET /batter/{id}/talent` — batter talent ELO
- `GET /pitcher/{id}/talent` — pitcher talent ELO
- `GET /predict/{batterId}/{pitcherId}` — server-side head-to-head prediction

### Fantasy (`/api/fantasy`)
- `GET /team-elo/all` — all 30 teams, ranked
- `GET /team-elo/{team_code}` — single team + 20-game trend
- `POST /roster` — parse roster text, fuzzy-match to DB
- `GET /schedule?week=` — MLB schedule for given week
- `POST /weekly-projection` — full weekly projection from roster + date
- `GET /matchup/{batterId}/{pitcherId}` — single matchup with fantasy points

### Export (`/api/fantasy/export`)
- `POST /pdf` — generate and download PDF report

## How the ELO System Works

### Player ELO
Each plate appearance is a zero-sum contest between batter and pitcher. The expected run value comes from RE24 baselines (run expectancy by base/out state), adjusted for park factors. ELO updates use:

```
K * (actual_delta_run_exp - expected_delta_run_exp)
```

### 9D Talent ELO
Five batter dimensions (contact, power, discipline, speed, clutch) and four pitcher dimensions (stuff, command, BIP suppression, clutch) track separate ELO ratings per plate appearance outcome.

### Team ELO
FiveThirtyEight-style ratings (K=4, home-field advantage=24 ELO points):

```
expected = 1 / (1 + 10^((away_elo - (home_elo + HFA)) / 400))
delta = K * log(|run_diff| + 1) * (actual - expected)
```

All ratings regress 1/3 toward 1500 at season start.

### Matchup Predictor
3-stage decision tree predicting plate appearance outcomes:
1. **Stage 1** — Softmax over BB / K / BIP using discipline/command and contact/stuff z-scores
2. **Stage 2** — Given ball in play: hit probability from contact/BIP-suppression
3. **Stage 3** — Given hit: XBH split (1B/2B/3B/HR) from power z-score

Output: per-PA probabilities for BB, K, OUT, 1B, 2B, 3B, HR + expected wOBA.

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Daily hot/cold players + daily fantasy points leaders/losers (batter & pitcher tabs), league summary |
| `/leaderboard` | Leaderboard | Player ELO rankings (Batter / Pitcher / Batter Fantasy / Pitcher Fantasy tabs) |
| `/talent-leaderboard` | Talent | 9D talent rankings |
| `/player/:playerId` | Player Profile | ELO history chart (toggleable to any talent dimension), last-5-games table, talent cards (Contact/Power/Discipline/Speed/Clutch) |
| `/matchup` | Matchup | Head-to-head batter vs pitcher prediction |
| `/team-elo` | Team ELO | All 30 teams ranked by ELO |
| `/team-elo/:teamCode` | Team Detail | Team ELO chart + game log |
| `/fantasy` | Fantasy Dashboard | Roster (pre-loaded) → weekly projections |
| `/fantasy/batters` | Batter Matchups | Full weekly batter grid |
| `/fantasy/pitchers` | Pitcher Matchups | Pitcher start projections |
| `/fantasy/matchup/:b/:p` | Matchup Detail | Single matchup deep dive |
| `/export` | Export | PDF report generation + download |
| `/guide` | Guide | ELO system explainer |

## Daily Automation

GitHub Actions runs at 8am EST daily (`.github/workflows/daily_update.yml`):

| Step | Action |
|------|--------|
| 1 | Update player ELO + talent from yesterday's games |
| 2 | Update team ELO from yesterday's results |
| 3 | Refresh Fangraphs batting + pitching stat caches |
| 4 | Fetch this week's MLB schedule + probable pitchers |
| 5 | Seed Speed ELO from MLB Stats API (SB/CS seasonal totals) |

All steps are idempotent (upsert/cache-skip). Manual trigger available via `workflow_dispatch`.

**Setup**: Add `SUPABASE_URL`, `SUPABASE_KEY`, and `DATABASE_URL` to GitHub repo Secrets (`Settings → Secrets → Actions`).

**Repo**: https://github.com/boerface16/Fantasy_ELO_Tool

## Roadmap

- [x] **Phase 0** — Project setup, FastAPI skeleton, frontend migration
- [x] **Phase 1** — Team ELO engine, backfill, API endpoints
- [x] **Phase 2** — Fantasy backend (roster parser, schedule fetcher, matchup predictor, weekly projections)
- [x] **Phase 3** — Fantasy frontend (roster upload, weekly grids, matchup detail pages)
- [x] **Phase 4** — PDF export, daily automation (GitHub Actions)

## License

Private project.
