# Fantasy Matchup Predictor — Setup Instructions

## Prerequisites

- Python 3.11+
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
# Process the full 2025 season (this takes a while)
python -m scripts.daily_elo --range 2025-03-27 2025-09-28
```

This fetches Statcast data for each date, runs the player ELO and 9D talent engines, and uploads results to Supabase.

### 3b. Backfill Team ELO

```bash
# Compute team ELO ratings from 2025 game results
python -m scripts.backfill_team_elo
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

Key endpoint groups:
- `/api/elo/*` — player ELO leaderboards, search, OHLC history
- `/api/talent/*` — 9D talent radar, talent leaderboards
- `/api/matchup/*` — batter vs pitcher talent lookup
- `/api/fantasy/*` — team ELO ratings and trends
- `/api/health` — health check

### Frontend (React + Vite)

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173`. Vite proxies `/api` requests to the FastAPI backend.

---

## 5. Running Tests

```bash
python -m pytest tests/ -v
```

---

## 6. Daily Updates (Incremental)

After the initial backfill, update data one day at a time:

```bash
# Update player ELO for yesterday's games
python -m scripts.daily_elo

# Update team ELO for yesterday's games
python -m scripts.backfill_team_elo --date YYYY-MM-DD
```

For automated daily updates, see the GitHub Actions workflow in `.github/workflows/daily_update.yml` (Phase 4).

---

## Project Structure

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
│   ├── fantasy/                    # Fantasy-specific modules (Phase 2+)
│   └── api/                        # FastAPI backend
│       ├── main.py                 # App entry point, CORS, router registration
│       ├── deps.py                 # Supabase client singleton
│       └── routers/
│           ├── elo.py              # Player ELO endpoints
│           ├── talent.py           # Talent radar/leaderboard endpoints
│           ├── matchup.py          # Matchup prediction endpoints
│           └── fantasy.py          # Team ELO + fantasy endpoints
├── scripts/
│   ├── daily_elo.py                # CLI for daily player ELO updates
│   ├── backfill_team_elo.py        # CLI for team ELO backfill
│   ├── compute_matchup_constants.py
│   └── migrations/                 # SQL migrations (001-006)
├── frontend/                       # React 19 + Vite + Tailwind
└── tests/
```

---

## Configuration Reference

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
