# Fantasy Matchup Predictor — Setup Instructions

## Prerequisites

- Python 3.11+ (tested on 3.12 in CI, 3.14 locally)
- Node.js 20+
- npm 10+
- A Supabase project (URL + anon key)

---

## 1. Environment Setup

```bash
# Clone / navigate to the project
cd fantasy-matchup-predictor

# Create .env from template
cp .env.example .env
# Edit .env with your Supabase credentials:
#   SUPABASE_URL=https://xxx.supabase.co
#   SUPABASE_KEY=eyJ...
#   DATABASE_URL=postgresql://postgres.xxx:YOUR_PASSWORD@host:5432/postgres
```

### Python

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

---

## 2. Database Migrations

Run each migration in order against your Supabase SQL Editor:

1. `scripts/migrations/001_create_tables.sql` — core tables (players, plate_appearances, player_elo, daily_ohlc)
2. `scripts/migrations/002_split_elo.sql` — split batting/pitching ELO columns
3. `scripts/migrations/003_k_modulation.sql` — K-factor modulation fields
4. `scripts/migrations/004_talent_schema.sql` — 9D talent system tables (talent_player_current, talent_pa_detail, talent_daily_ohlc)
5. `scripts/migrations/005_talent_rpc.sql` — RPC functions for talent radar queries
6. `scripts/migrations/006_team_elo.sql` — team ELO table (FiveThirtyEight-style)

---

## 3. Data Loading

### 3a. Load Statcast Data + Player ELO

```bash
# Load full 2025 season (wipes any existing data — always use --fresh first time)
python -m scripts.bulk_load --end-date 2025-09-28 --fresh

# Load 2026 season from opening day (incremental — does not wipe 2025)
python -m scripts.bulk_load --start-date 2026-03-18

# Load a specific date range only
python -m scripts.bulk_load --start-date 2026-04-01 --end-date 2026-04-07
```

`--fresh` wipes ELO tables and recomputes from scratch. Use it whenever data looks wrong or you're loading for the first time.

### 3b. Backfill Team ELO

```bash
# Full recompute from all plate_appearances (use --fresh after any bulk_load --fresh)
python -m scripts.backfill_team_elo --fresh

# Incremental: single date or range
python -m scripts.backfill_team_elo --date 2026-04-01
python -m scripts.backfill_team_elo --range 2026-04-01 2026-04-07
```

### 3c. Compute Matchup Constants

```bash
python scripts/compute_matchup_constants.py
```

Generates the ELO distribution statistics used by the matchup predictor.

---

## 4. Running the App

### Backend (FastAPI)

```bash
uvicorn src.api.main:app --reload
```

Runs on `http://localhost:8000`. API docs at `/docs`.

### Frontend (React + Vite)

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173`. Vite proxies `/api` requests to the FastAPI backend.

---

## 5. API Endpoints

### Player ELO (`/api/elo`)
- `GET /leaderboard` — ELO rankings by position
- `GET /players/{id}` — player detail + OHLC chart data
- `GET /players/{id}/ohlc` — OHLC candlestick data
- `GET /players/{id}/stats` — player stats
- `GET /hot-players` / `cold-players` — streaking players
- `GET /search?q=` — fuzzy player search
- `GET /league-summary` — league-wide ELO stats
- `GET /latest-date` / `season-meta` — date/season info

### Talent ELO (`/api/talent`)
- `GET /leaderboard` — 9D talent rankings
- `GET /players/{id}/radar` — radar chart data

### Matchup (`/api/matchup`)
- `GET /batter/{id}/talent` — batter talent ELO
- `GET /pitcher/{id}/talent` — pitcher talent ELO
- `GET /predict/{batterId}/{pitcherId}` — head-to-head prediction

### Fantasy (`/api/fantasy`)
- `GET /team-elo/all` — all 30 teams, ranked
- `GET /team-elo/{team_code}` — single team + 20-game trend
- `POST /roster` — parse roster text, fuzzy-match to DB
- `GET /schedule?week=` — MLB schedule for given week
- `POST /weekly-projection` — full weekly projection from roster + date
- `GET /matchup/{batterId}/{pitcherId}` — single matchup with fantasy points

### Export (`/api/fantasy/export`)
- `POST /pdf` — generate and download PDF report

### Health
- `GET /api/health` — health check

---

## 6. Running Tests

```bash
python -m pytest tests/ -v
```

112 tests across 9 test files covering all fantasy modules, team ELO engine, and matchup predictor.

> **Note on Python 3.14**: All dependencies must be installed at once:
> `python -m pip install -r requirements.txt`
> Installing packages one-by-one can fail due to missing `psycopg2`, `dotenv`, or other deps.

---

## 7. Daily Updates

### Automated (GitHub Actions)

The daily pipeline runs automatically at 8am EST via `.github/workflows/daily_update.yml`. See the [Pipeline Guide](pipeline-guide.md) for setup.

### Manual

```bash
# Full daily pipeline (player ELO, team ELO, Fangraphs cache, schedule)
python -m scripts.run_daily

# Specific date
python -m scripts.run_daily --date 2026-04-01

# Team ELO only (incremental)
python -m scripts.backfill_team_elo --date 2026-04-01

# Team ELO full recompute
python -m scripts.backfill_team_elo --fresh
```

---

## 8. Project Structure

```
fantasy-matchup-predictor/
├── config/
│   ├── multi_elo_config.yaml       # 9D talent engine parameters
│   ├── espn_scoring.yaml           # ESPN H2H points scoring rules
│   └── team_elo_config.yaml        # Team ELO parameters (K=4, HFA=24)
├── data/
│   ├── mlb_park_factors.csv        # Park factor adjustments
│   └── mlb_re24_baseline.csv       # Run expectancy baseline
├── src/
│   ├── engine/                     # ELO calculation engines
│   │   ├── elo_calculator.py       # V5.3 zero-sum player ELO
│   │   ├── elo_batch.py            # Batch player ELO processing
│   │   ├── multi_elo_engine.py     # 9D talent engine
│   │   ├── talent_batch.py         # Batch talent processing
│   │   └── team_elo_engine.py      # FiveThirtyEight-style team ELO
│   ├── etl/                        # Data extraction and loading
│   ├── pipeline/                   # Daily pipeline orchestration
│   ├── fantasy/                    # Fantasy modules
│   │   ├── roster_parser.py        # Parse ESPN roster text, fuzzy-match
│   │   ├── schedule_fetcher.py     # MLB Stats API for probable pitchers
│   │   ├── opponent_resolver.py    # Roster × schedule → matchup tuples
│   │   ├── elo_lookup.py           # Batch talent ELO queries + cache
│   │   ├── matchup_predictor.py    # 3-stage PA prediction (Python port)
│   │   ├── fantasy_calculator.py   # Probabilities → ESPN fantasy points
│   │   ├── weekly_projection.py    # Full weekly orchestrator
│   │   ├── fangraphs_enricher.py   # pybaseball wrapper with daily cache
│   │   └── report.py              # reportlab PDF generation
│   └── api/                        # FastAPI backend
│       ├── main.py                 # App entry point, CORS, router registration
│       ├── deps.py                 # Supabase client singleton
│       └── routers/
│           ├── elo.py              # Player ELO endpoints
│           ├── talent.py           # Talent radar/leaderboard endpoints
│           ├── matchup.py          # Matchup prediction endpoints
│           ├── fantasy.py          # Team ELO + fantasy endpoints
│           └── export.py           # PDF export endpoint
├── scripts/
│   ├── bulk_load.py                # Fast data loader (psycopg2, ~90s)
│   ├── daily_elo.py                # CLI for daily player ELO updates
│   ├── backfill_team_elo.py        # CLI for team ELO backfill
│   ├── run_daily.py                # Daily pipeline orchestrator (4 steps)
│   ├── run_weekly.py               # Weekly Fangraphs cache refresh
│   ├── compute_matchup_constants.py
│   └── migrations/                 # SQL migrations (001-006)
├── frontend/                       # React 19 + Vite + Tailwind v4
│   └── src/
│       ├── pages/                  # 11 pages (Dashboard, Fantasy, Export, etc.)
│       └── components/
│           ├── matchup/            # Matchup visualization components
│           └── fantasy/            # Fantasy-specific components (7)
├── .github/workflows/
│   └── daily_update.yml            # GitHub Actions daily automation
├── .cache/                         # Fangraphs daily cache (gitignored)
└── tests/                          # pytest test suite (112 tests)
```

---

## 9. Configuration Reference

### `config/team_elo_config.yaml`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initial_elo` | 1500.0 | Starting ELO for new teams |
| `k_factor` | 4.0 | Base K-factor (lower than player ELO — team form is slower-moving) |
| `home_field_advantage` | 24.0 | ELO points added to home team for expected score calculation |
| `season_regression_fraction` | 0.333 | Regress 1/3 toward 1500 at season boundary |
| `elo_divisor` | 400.0 | Standard ELO divisor |

### `config/espn_scoring.yaml`

ESPN H2H Points league scoring weights. See file for full breakdown.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/service key |
| `DATABASE_URL` | For bulk_load | Direct PostgreSQL connection string |
