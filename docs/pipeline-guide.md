# Fantasy Matchup Predictor — Pipeline Guide

Complete guide to running every part of the pipeline, from initial setup to daily automation to deploying a live site.

---

## 1. Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Backend, ELO engines, data pipeline |
| Node.js | 20+ | Frontend build and dev server |
| npm | 10+ | Frontend package management |
| Supabase project | Free tier works | PostgreSQL database + REST API |

### Environment Variables

Create `.env` in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Required variables:

| Variable | Example | Used By |
|----------|---------|---------|
| `SUPABASE_URL` | `https://abc123.supabase.co` | All backend scripts, FastAPI |
| `SUPABASE_KEY` | `eyJhbGc...` (anon key) | All backend scripts, FastAPI |
| `DATABASE_URL` | `postgresql://postgres.abc:PASS@aws-0-us-east-2.pooler.supabase.com:5432/postgres` | `bulk_load.py` (psycopg2 direct connection) |

### Install Dependencies

```bash
# Python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

---

## 2. Database Setup

Run each migration in order in the **Supabase SQL Editor** (Dashboard → SQL Editor → New Query):

| Migration | What It Creates |
|-----------|----------------|
| `scripts/migrations/001_create_tables.sql` | `players`, `plate_appearances`, `player_elo`, `elo_pa_detail`, `daily_ohlc` |
| `scripts/migrations/002_split_elo.sql` | Splits ELO into `on_base_elo` and `power_elo` columns |
| `scripts/migrations/003_k_modulation.sql` | K-factor scaling based on PA count |
| `scripts/migrations/004_talent_schema.sql` | `talent_player_current`, `talent_pa_detail`, `talent_daily_ohlc` (9D talent system) |
| `scripts/migrations/005_talent_rpc.sql` | RPC functions for talent radar queries |
| `scripts/migrations/006_team_elo.sql` | `team_elo` table (FiveThirtyEight-style team ratings) |

---

## 3. Initial Data Load

This is a one-time process to populate the database with historical data.

### Step 1: Load Statcast Data + Compute Player ELO

```bash
python -m scripts.bulk_load
```

**What it does:**
- Fetches 2025 Statcast data via pybaseball (monthly chunks)
- Uploads plate appearances via psycopg2 (direct PostgreSQL, not REST — ~90 seconds vs 60+ minutes)
- Computes player ELO and 9D talent ELO for every batter and pitcher
- Generates daily OHLC candlestick data per player

**Expected output:**
```
183,092 plate appearances loaded
1,469 players tracked
Date range: 2025-03-27 → 2025-09-28
```

### Step 2: Backfill Team ELO

```bash
python -m scripts.backfill_team_elo
```

**What it does:**
- Reads game results from `plate_appearances` (deduces final scores)
- Computes FiveThirtyEight-style team ELO (K=4, home-field advantage=24, MOV multiplier)
- Uploads to `team_elo` table

**Expected output:**
```
30 teams with ELO ratings
NYY #1 (1561), COL #30 (1353)
~2,430 game records
```

### Step 3: Verify

```bash
# Start the API
uvicorn src.api.main:app --reload

# Test endpoints
curl http://localhost:8000/api/health
curl http://localhost:8000/api/fantasy/team-elo/all
curl http://localhost:8000/api/elo/leaderboard
```

---

## 4. Running the Application

### Backend (FastAPI)

```bash
uvicorn src.api.main:app --reload
```

Runs on `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### Frontend (React + Vite)

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173`. Vite proxies all `/api` requests to the FastAPI backend automatically.

### Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Daily hot/cold players, league summary |
| `/leaderboard` | Leaderboard | Player ELO rankings by position |
| `/talent-leaderboard` | Talent | 9D talent rankings with radar charts |
| `/player/:id` | Player Profile | Individual player detail + OHLC chart |
| `/matchup` | Matchup | Interactive batter vs pitcher prediction |
| `/fantasy` | Fantasy Dashboard | Paste roster → pick week → get projections |
| `/fantasy/batters` | Batter Matchups | Full weekly batter grid (rows × days) |
| `/fantasy/pitchers` | Pitcher Matchups | Pitcher start projections |
| `/fantasy/matchup/:b/:p` | Matchup Detail | Single matchup deep dive with z-scores |
| `/export` | Export | PDF report generation + download |
| `/guide` | Guide | ELO system explainer |

---

## 5. Daily Pipeline

The daily pipeline updates all data after each day's games. It runs automatically via GitHub Actions at 8am EST, or manually:

```bash
# Process yesterday's games (default)
python -m scripts.run_daily

# Process a specific date
python -m scripts.run_daily --date 2025-09-28
```

### What Each Step Does

| Step | Module | Action | Idempotent? |
|------|--------|--------|-------------|
| 1 | `daily_pipeline` | Fetch new PAs, update player ELO + 9D talent ELO | Yes (upsert) |
| 2 | `backfill_team_elo` | Compute team ELO from game results for target date | Yes (upsert on conflict) |
| 3 | `fangraphs_enricher` | Cache season batting + pitching stats as parquet files | Yes (skip if today's cache exists) |
| 4 | `schedule_fetcher` | Fetch this week's MLB schedule + probable pitchers | Yes (overwrite) |

**Expected output:**
```
============================================================
DAILY PIPELINE — 2025-09-28
============================================================

Step 1/4: Player ELO + Talent update...
  Status: success
  PAs: 487, Players: 312

Step 2/4: Team ELO update...
  Team ELO updated

Step 3/4: Fangraphs cache refresh...
  Cached 542 batters, 389 pitchers

Step 4/4: Schedule fetch...
  Fetched 15 games for this week

============================================================
DAILY PIPELINE SUMMARY
============================================================
  [OK] player_elo: success
  [OK] team_elo: success
  [OK] fangraphs: success
  [OK] schedule: success
============================================================
```

### Other Daily Scripts

```bash
# Player ELO only (more granular control)
python -m scripts.daily_elo --date 2025-09-28
python -m scripts.daily_elo --range 2025-09-01 2025-09-28

# Team ELO only
python -m scripts.backfill_team_elo --date 2025-09-28
python -m scripts.backfill_team_elo --range 2025-09-01 2025-09-28
```

---

## 6. Weekly Cache Refresh

Refreshes Fangraphs batting and pitching stat caches on demand:

```bash
# Current season
python -m scripts.run_weekly

# Specific season
python -m scripts.run_weekly --season 2025
```

Cache files are stored in `.cache/` as parquet files (`batting_2025_2026-03-31.parquet`). Old caches are automatically cleaned up — only today's file is kept per stat type.

---

## 7. Fantasy Projection Workflow

This is the core user-facing feature. Here's the end-to-end flow:

### Step 1: Paste Roster

On the `/fantasy` page, paste your ESPN roster. Supported formats:

**ESPN tab format** (copy from My Team page):
```
C	Salvador Perez, KC C
1B	Vladimir Guerrero Jr., TOR 1B
OF	Aaron Judge, NYY OF
SP	Gerrit Cole, NYY SP
```

**CSV format:**
```
C,Salvador Perez,KC
1B,Vladimir Guerrero Jr.,TOR
```

**Simple names** (one per line):
```
Aaron Judge
Gerrit Cole
```

### Step 2: Click "Parse Roster"

The frontend calls `POST /api/fantasy/roster` which:
- Extracts slot, name, and team from each line
- Fuzzy-matches names against the `players` table (handles typos/nicknames)
- Returns matched `player_id`, `full_name`, `position`, and `team` for each entry

### Step 3: Select Week & Project

Pick a week (Monday-Sunday) using the week selector, then click **"Project Week"**.

The backend (`POST /api/fantasy/weekly-projection`) runs the full pipeline:

1. **Parse roster** → list of `RosterEntry` objects
2. **Fetch schedule** → MLB games for that week with probable pitchers
3. **Resolve opponents** → for each batter: which pitcher they face each day; for each pitcher: which team they face
4. **Load ELO** → batch query `talent_player_current` for all relevant pitcher IDs
5. **Predict matchups** → 3-stage decision tree per plate appearance:
   - Stage 1: Softmax over BB / K / BIP (discipline/command + contact/stuff z-scores)
   - Stage 2: Given BIP → hit probability (contact vs BIP-suppression)
   - Stage 3: Given hit → XBH split (1B/2B/3B/HR from power z-score)
6. **Calculate fantasy points** → apply ESPN scoring weights (TB, R, RBI, BB, SB, SO for batters; IP, K, W, SV, HD, H, ER, BB, L for pitchers)

### Step 4: View Results

The dashboard shows:
- **Points summary** — total, batter, pitcher breakdown
- **Batter grid** — rows per batter, columns per day, cells show opponent + projected points
- **Pitcher grid** — starts, opponents, projected points
- **Team ELO rankings** — all 30 teams sorted by current ELO

Click any matchup cell to see the full prediction breakdown on the detail page.

### Step 5: Drill Down

- `/fantasy/batters` — full-width batter grid with color-coded wOBA cells
- `/fantasy/pitchers` — pitcher projections with start details
- `/fantasy/matchup/:batterId/:pitcherId` — single matchup showing z-score differentials, outcome probabilities, expected wOBA, and fantasy points

---

## 8. PDF Export

### Via Frontend

1. Navigate to `/export`
2. Paste your ESPN roster
3. Select week start date
4. Click **"Generate PDF"**
5. PDF downloads automatically as `fantasy-report-{date}.pdf`

### Via API

```bash
curl -X POST http://localhost:8000/api/fantasy/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"roster_text": "OF\tAaron Judge, NYY OF\nSP\tGerrit Cole, NYY SP", "ref_date": "2025-09-22"}' \
  -o fantasy-report.pdf
```

### PDF Contents

- **Title page** — week range + generation date
- **Summary table** — total / batter / pitcher projected points
- **Batter projections** — sorted by total points, with per-game matchup details
- **Pitcher projections** — sorted by total points, with start details
- **Team ELO rankings** — all 30 teams ranked

---

## 9. GitHub Actions Automation

The daily pipeline runs automatically via GitHub Actions.

### Setup

1. Push the repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add these repository secrets:

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon key |
| `DATABASE_URL` | `postgresql://postgres.xxx:PASS@host:5432/postgres` |

### Schedule

The workflow (`.github/workflows/daily_update.yml`) runs:
- **Automatically**: Every day at **8:00 AM EST** (1:00 PM UTC)
- **Manually**: Click **"Run workflow"** in the Actions tab, optionally specifying a date

### Resource Usage

- ~5 minutes per run
- ~150 min/month (well within GitHub Actions free tier of 2,000 min/month)
- Built-in email notification on failure

---

## 10. Testing

```bash
# Run all 112 tests
python -m pytest tests/ -q

# Verbose output
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_roster_parser.py

# Filter by name
python -m pytest -k "weekly"
```

### Test Inventory

| Test File | Module | Tests |
|-----------|--------|-------|
| `test_team_elo_engine.py` | Team ELO engine | 20 |
| `test_matchup_predictor_py.py` | 3-stage PA predictor | 24 |
| `test_roster_parser.py` | Roster parsing + fuzzy match | 11 |
| `test_schedule_fetcher.py` | MLB Stats API schedule | 9 |
| `test_opponent_resolver.py` | Roster × schedule resolution | 7 |
| `test_elo_lookup.py` | Batch talent ELO queries | 7 |
| `test_fangraphs_enricher.py` | pybaseball cache wrapper | 14 |
| `test_fantasy_calculator.py` | ESPN points calculation | 12 |
| `test_weekly_projection.py` | Full orchestration | 8 |

All tests use mocks for external services (Supabase, MLB Stats API, pybaseball) and run without network access.

---

## 11. Deploying to a Live Website

### Option A: Railway (Recommended)

[Railway](https://railway.app) is the simplest option — it supports Python + Node in one project, has a free tier, and auto-deploys from GitHub.

**Steps:**

1. Push repo to GitHub
2. Sign up at [railway.app](https://railway.app) and connect your GitHub repo
3. Railway auto-detects Python — add a `Procfile`:
   ```
   web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
   ```
4. Add environment variables in Railway dashboard:
   - `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`
5. For the frontend, build static assets and serve from FastAPI:
   ```bash
   cd frontend && npm run build
   ```
   Then mount the `frontend/dist/` directory in FastAPI (see "Serving Frontend from FastAPI" below)
6. Railway assigns a URL like `your-app.up.railway.app` — add a custom domain in settings if desired

**Cost:** Free tier includes 500 hours/month + 100 GB bandwidth. Hobby plan ($5/month) for always-on.

### Option B: Render

[Render](https://render.com) is similar to Railway with a generous free tier.

**Steps:**

1. Push repo to GitHub
2. Create a **Web Service** on Render, connect your repo
3. Set build command: `pip install -r requirements.txt && cd frontend && npm install && npm run build`
4. Set start command: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in Render dashboard
6. Render assigns a URL like `your-app.onrender.com`

**Note:** Render free tier spins down after 15 minutes of inactivity (cold starts take ~30 seconds).

### Option C: Vercel (Frontend) + Railway (Backend)

Best if you want fast global CDN for the frontend:

1. Deploy frontend to [Vercel](https://vercel.com): `cd frontend && vercel`
2. Deploy backend to Railway (see Option A)
3. Update `frontend/.env.production` with the Railway API URL:
   ```
   VITE_API_URL=https://your-backend.up.railway.app
   ```
4. Update `apiClient.ts` to use `VITE_API_URL` as the base URL in production
5. Update CORS in `src/api/main.py` to allow your Vercel domain

### Option D: VPS (Full Control)

For maximum control, deploy to a VPS (DigitalOcean, Linode, Hetzner):

```bash
# On the server
git clone your-repo
cd fantasy-matchup-predictor
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# Run with gunicorn + uvicorn workers
pip install gunicorn
gunicorn src.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Use nginx as reverse proxy + serve frontend static files
# Use systemd to keep the process running
# Use certbot for HTTPS
```

### Comparison

| | Railway | Render | Vercel + Railway | VPS |
|--|---------|--------|------------------|-----|
| **Ease of setup** | Easiest | Easy | Medium | Hardest |
| **Free tier** | 500 hrs/mo | 750 hrs/mo (cold starts) | Generous | No |
| **Custom domain** | Yes | Yes | Yes | Yes |
| **Auto-deploy** | Yes (GitHub) | Yes (GitHub) | Yes (GitHub) | Manual or CI |
| **Always-on** | Hobby $5/mo | Paid plans | Backend: $5/mo | $4-6/mo |
| **Best for** | Quick launch | Budget | Performance | Full control |

### Serving Frontend from FastAPI (Single-Origin Deploy)

For Railway/Render, serve the built frontend from FastAPI to avoid CORS issues:

```python
# Add to src/api/main.py after router registration
from fastapi.staticfiles import StaticFiles
import os

# Serve frontend build (after npm run build)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
```

Build the frontend before deploying:
```bash
cd frontend && npm run build
```

This serves the React app at `/` and the API at `/api/*` from the same origin — no CORS configuration needed.

### Production CORS

If deploying frontend and backend separately, update `src/api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",        # Dev
        "https://your-app.vercel.app",  # Production frontend
        "https://yourdomain.com",       # Custom domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 12. Troubleshooting

### Stale Fangraphs Cache

If stats seem outdated, force a cache refresh:
```bash
# Delete today's cache files
rm .cache/batting_*.parquet .cache/pitching_*.parquet

# Re-fetch
python -m scripts.run_weekly
```

### pybaseball Rate Limits

Baseball Reference limits to ~10 requests/minute. If you see 429 errors:
- Wait 60 seconds and retry
- The daily parquet cache prevents repeated calls — once cached, no more API calls that day

### Missing Environment Variables

If scripts fail with `SUPABASE_URL not set`:
- Ensure `.env` exists in the project root
- Ensure `python-dotenv` is installed (`pip install python-dotenv`)
- Scripts load `.env` automatically via `dotenv.load_dotenv()`

### Database Connection Issues

If `bulk_load.py` fails with connection errors:
- Check `DATABASE_URL` format: `postgresql://postgres.PROJECT_REF:PASSWORD@HOST:5432/postgres`
- Ensure password is URL-encoded (special characters like `@` or `#` need encoding)
- Try connecting manually: `psql $DATABASE_URL`

### Frontend Proxy Not Working

If the frontend can't reach the API:
- Ensure FastAPI is running on port 8000: `uvicorn src.api.main:app --reload`
- Check `frontend/vite.config.ts` has the proxy configured for `/api`
- The proxy only works in dev mode (`npm run dev`), not in production builds

### GitHub Actions Failures

- Check the Actions tab in your GitHub repo for logs
- Verify all 3 secrets are set: `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`
- Use **"Run workflow"** button to manually trigger and test
- GitHub sends email notifications on failure automatically
