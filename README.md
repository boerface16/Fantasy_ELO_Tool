# Fantasy Matchup Predictor

A fantasy baseball tool that combines MLB ELO ratings with ESPN H2H points scoring to project weekly matchups. Built on FiveThirtyEight-style ELO systems for both individual players and teams, with a 9-dimensional talent model tracking power, discipline, speed, contact, and pitching skills.

## What It Does

- **Player ELO** — zero-sum ratings for every MLB batter and pitcher, updated per plate appearance
- **9D Talent ELO** — separate ELO tracks for power, discipline, speed, contact, eye (batters) and stuff, command, stamina, groundball tendency (pitchers)
- **Team ELO** — FiveThirtyEight-style team ratings with home-field advantage, margin-of-victory scaling, and season regression
- **Fantasy Projections** *(Phase 2+)* — combine ELO matchup predictions with ESPN scoring rules to project weekly fantasy points

## Current Status

**Phase 1 complete.** Player ELO, talent ELO, and team ELO engines are fully operational with 2025 season data loaded.

| Metric | Value |
|--------|-------|
| Plate appearances | 183,092 |
| Date range | 2025-03-27 → 2025-09-28 |
| Players tracked | 1,469 |
| Teams tracked | 30 |

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, Supabase (PostgreSQL) |
| Frontend | React 19, Vite, Tailwind CSS, TanStack Query |
| Data | pybaseball (Statcast), MLB Stats API |
| ELO Engine | Custom Python — zero-sum with park factors, RE24 baselines |

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

# Load 2025 season data (~2 minutes)
python -m scripts.bulk_load

# Backfill team ELO
python -m scripts.backfill_team_elo

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

## Project Structure

```
├── config/                  # YAML configs (ELO params, ESPN scoring)
├── data/                    # Static data (park factors, RE24 baselines)
├── src/
│   ├── engine/              # ELO engines (player, talent, team)
│   ├── etl/                 # Statcast → plate appearances pipeline
│   ├── pipeline/            # Daily update orchestration
│   ├── api/                 # FastAPI backend
│   │   └── routers/         # elo, talent, matchup, fantasy endpoints
│   └── fantasy/             # (Phase 2) Roster, schedule, projections
├── scripts/
│   ├── bulk_load.py         # Fast data loader (psycopg2, ~90s)
│   ├── backfill_team_elo.py # Compute team ELO from game results
│   └── migrations/          # SQL migrations (001-006)
├── frontend/                # React 19 + Vite + Tailwind
└── tests/                   # pytest test suite
```

## API Endpoints

### Player ELO
- `GET /api/elo/leaderboard` — ELO rankings by position
- `GET /api/elo/players/{id}` — player detail + OHLC chart data
- `GET /api/elo/hot-players` / `cold-players` — streaking players
- `GET /api/elo/search?q=` — fuzzy player search

### Talent ELO
- `GET /api/talent/leaderboard` — 9D talent rankings
- `GET /api/talent/players/{id}/radar` — radar chart data

### Matchup
- `GET /api/matchup/predict/{batterId}/{pitcherId}` — head-to-head prediction

### Team ELO
- `GET /api/fantasy/team-elo/all` — all 30 teams, ranked
- `GET /api/fantasy/team-elo/{team_code}` — single team + 20-game trend

## How the ELO System Works

### Player ELO
Each plate appearance is a zero-sum contest between batter and pitcher. The expected run value comes from RE24 baselines (run expectancy by base/out state), adjusted for park factors. ELO updates use:

```
K * (actual_delta_run_exp - expected_delta_run_exp)
```

### Team ELO
FiveThirtyEight-style ratings (K=4, home-field advantage=24 ELO points):

```
expected = 1 / (1 + 10^((away_elo - (home_elo + HFA)) / 400))
delta = K * log(|run_diff| + 1) * (actual - expected)
```

All ratings regress 1/3 toward 1500 at season start.

## Roadmap

- [x] **Phase 0** — Project setup, FastAPI skeleton, frontend migration
- [x] **Phase 1** — Team ELO engine, backfill, API endpoints
- [ ] **Phase 2** — Fantasy backend (roster parser, schedule fetcher, matchup predictor, weekly projections)
- [ ] **Phase 3** — Fantasy frontend (roster upload, weekly grids, matchup detail pages)
- [ ] **Phase 4** — PDF export, daily automation (GitHub Actions)

## License

Private project.
