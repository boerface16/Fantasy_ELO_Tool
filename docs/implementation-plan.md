# Fantasy Matchup Predictor — Standalone Project Plan

## Status: Phase 0 COMPLETE (2026-03-24)

**What's done:**
- 84 files copied from mlb-elo-demo-2025-main-GITHUB
- FastAPI backend skeleton: `src/api/` with 14 endpoints across 3 routers (elo, talent, matchup)
- Frontend migrated: all API files rewritten to use `apiClient.ts` (no more direct Supabase)
- Vite proxy configured, `@supabase/supabase-js` removed from frontend
- Config files: `requirements.txt`, `.gitignore`, `espn_scoring.yaml`, `006_team_elo.sql`

**Next: Phase 1 — Team ELO Engine**

---

## Context

Build a new standalone Fantasy Matchup Predictor app in a **separate directory** outside the existing `mlb-elo-demo-2025-main-GITHUB` repo. Necessary files (ELO engine, matchup predictor, ETL, configs) will be **copied** from the existing repo — nothing in the source repo is modified.

The app combines the existing ELO system with ESPN fantasy baseball features: roster management, weekly schedule/matchup projections, team ELO, Fangraphs enrichment, and PDF reports. Unified FastAPI backend serves everything.

### Key Decisions
- **Separate directory** — new project, copies needed files from existing repo
- **Unified FastAPI backend** — all data served via Python API
- **React 19 + Vite + Tailwind frontend** — same stack as existing app
- **Roster input via browser** — paste/upload in React UI
- **Demo with 2025 data**, architect for live 2026 season
- **Daily automation** — GitHub Actions at 8am EST

---

## Project Structure

```
fantasy-matchup-predictor/
├── .env                                    # SUPABASE_URL, SUPABASE_KEY
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── roster.md                               # Sample roster for reference
│
├── config/
│   ├── multi_elo_config.yaml               # COPY from existing repo
│   └── espn_scoring.yaml                   # NEW: ESPN H2H points rules
│
├── data/
│   ├── mlb_park_factors.csv                # COPY from existing repo
│   └── mlb_re24_baseline.csv              # COPY from existing repo
│
├── src/
│   ├── __init__.py
│   │
│   ├── engine/                             # COPIED from existing repo
│   │   ├── __init__.py
│   │   ├── elo_calculator.py               # COPY: V5.3 zero-sum ELO
│   │   ├── elo_batch.py                    # COPY: batch processing
│   │   ├── multi_elo_engine.py             # COPY: 9D talent engine
│   │   ├── talent_batch.py                 # COPY: talent batch processing
│   │   └── team_elo_engine.py              # NEW: FiveThirtyEight-style team ELO
│   │
│   ├── etl/                                # COPIED from existing repo
│   │   ├── __init__.py
│   │   ├── statcast_to_pa.py               # COPY
│   │   ├── event_mapper.py                 # COPY
│   │   ├── player_lookup.py                # COPY
│   │   ├── player_registry.py              # COPY
│   │   ├── fetch_statcast.py               # COPY
│   │   └── upload_to_supabase.py           # COPY
│   │
│   ├── fantasy/                            # ALL NEW
│   │   ├── __init__.py
│   │   ├── roster_parser.py                # Parse pasted roster text, fuzzy-match names
│   │   ├── schedule_fetcher.py             # MLB Stats API for probable pitchers
│   │   ├── opponent_resolver.py            # Map roster → weekly opponents
│   │   ├── elo_lookup.py                   # Batch player + team ELO from Supabase
│   │   ├── fangraphs_enricher.py           # pybaseball wrapper with daily cache
│   │   ├── matchup_predictor.py            # Port of matchupPredictor.ts to Python
│   │   ├── fantasy_calculator.py           # ESPN fantasy points estimation
│   │   ├── weekly_projection.py            # Orchestrator: full weekly pipeline
│   │   └── report.py                       # PDF generation via reportlab
│   │
│   └── api/                                # ALL NEW — unified FastAPI backend
│       ├── __init__.py
│       ├── main.py                         # FastAPI app, CORS, lifespan
│       ├── deps.py                         # Supabase client singleton, caching
│       └── routers/
│           ├── __init__.py
│           ├── elo.py                      # ELO leaderboard/player/search endpoints
│           ├── talent.py                   # Talent leaderboard/radar endpoints
│           ├── matchup.py                  # Single matchup prediction endpoint
│           ├── fantasy.py                  # Roster, schedule, weekly projection endpoints
│           └── export.py                   # PDF export endpoint
│
├── scripts/
│   ├── run_daily.py                        # Daily pipeline orchestrator (all 5 steps)
│   ├── run_weekly.py                       # Manual: regenerate weekly projections
│   ├── backfill_team_elo.py                # One-time: compute team ELO from 2025 data
│   ├── compute_matchup_constants.py        # COPY from existing repo
│   └── migrations/
│       ├── 001_create_tables.sql           # COPY from existing repo
│       ├── 002_through_005.sql             # COPY all existing migrations
│       └── 006_team_elo.sql                # NEW: team_elo table
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── App.tsx                         # Router: ELO pages + fantasy pages
│       ├── main.tsx
│       ├── lib/
│       │   ├── apiClient.ts               # Fetch wrapper → FastAPI
│       │   └── matchupPredictor.ts         # COPY: client-side predictor for instant UI
│       ├── api/
│       │   ├── elo.ts                      # API calls (via apiClient, NOT direct Supabase)
│       │   ├── talent.ts
│       │   ├── matchup.ts
│       │   └── fantasy.ts                  # NEW: fantasy API calls
│       ├── hooks/
│       │   ├── useElo.ts                   # COPY + modify: use apiClient
│       │   ├── useMatchup.ts               # COPY + modify
│       │   ├── useTalent.ts                # COPY + modify
│       │   └── useFantasy.ts               # NEW: React Query hooks for fantasy
│       ├── types/
│       │   ├── elo.ts                      # COPY from existing repo
│       │   ├── talent.ts                   # COPY from existing repo
│       │   ├── matchup.ts                  # COPY from existing repo
│       │   └── fantasy.ts                  # NEW: fantasy TypeScript interfaces
│       ├── pages/
│       │   ├── Dashboard.tsx               # COPY from existing (ELO dashboard)
│       │   ├── Leaderboard.tsx             # COPY
│       │   ├── PlayerProfile.tsx           # COPY
│       │   ├── TalentLeaderboard.tsx       # COPY
│       │   ├── MatchupPredictor.tsx        # COPY
│       │   ├── Guide.tsx                   # COPY
│       │   ├── FantasyDashboard.tsx        # NEW: roster upload + week summary
│       │   ├── BatterMatchups.tsx          # NEW: weekly batter grid
│       │   ├── PitcherMatchups.tsx         # NEW: pitcher projection view
│       │   ├── FantasyMatchupDetail.tsx    # NEW: enhanced single matchup
│       │   └── ExportPage.tsx              # NEW: PDF trigger + download
│       └── components/
│           ├── matchup/                    # COPY all existing matchup components
│           │   ├── MatchupBar.tsx
│           │   ├── StageResults.tsx
│           │   └── FinalPrediction.tsx
│           ├── ui/                         # COPY shared UI components
│           └── fantasy/                    # ALL NEW
│               ├── RosterUpload.tsx        # Paste area + file upload
│               ├── WeekSelector.tsx        # Mon-Sun week picker
│               ├── WeeklyGrid.tsx          # Batter matchup table
│               ├── PitcherGrid.tsx         # Pitcher matchup table
│               ├── FantasyPointsPanel.tsx  # ESPN points breakdown card
│               ├── TeamEloBadge.tsx        # Hot/cold team indicator
│               └── FangraphsSidebar.tsx    # wRC+, ERA- context display
│
├── .cache/                                 # Fangraphs daily cache (gitignored)
├── logs/                                   # Daily run logs (gitignored)
│
├── .github/
│   └── workflows/
│       └── daily_update.yml                # GitHub Actions: 8am EST daily pipeline
│
└── tests/
    ├── test_team_elo_engine.py
    ├── test_matchup_predictor_py.py        # Cross-validate Python vs TS output
    ├── test_roster_parser.py
    ├── test_fantasy_calculator.py
    ├── test_opponent_resolver.py
    ├── test_weekly_projection.py
    ├── test_api_elo_endpoints.py
    └── test_api_fantasy_endpoints.py
```

---

## Files to Copy from Existing Repo

Everything listed below is **read-only copy** — the source repo is not modified.

### Python (src/)
| Source path | Destination | Notes |
|-------------|-------------|-------|
| `src/engine/elo_calculator.py` | `src/engine/elo_calculator.py` | As-is |
| `src/engine/elo_batch.py` | `src/engine/elo_batch.py` | As-is |
| `src/engine/multi_elo_engine.py` | `src/engine/multi_elo_engine.py` | As-is |
| `src/engine/talent_batch.py` | `src/engine/talent_batch.py` | As-is |
| `src/etl/*.py` (all 6 files) | `src/etl/*.py` | As-is |
| `scripts/compute_matchup_constants.py` | `scripts/compute_matchup_constants.py` | As-is |
| `scripts/daily_elo.py` | `scripts/daily_elo.py` | As-is |

### Config & Data
| Source path | Destination | Notes |
|-------------|-------------|-------|
| `config/multi_elo_config.yaml` | `config/multi_elo_config.yaml` | As-is |
| `data/mlb_park_factors.csv` | `data/mlb_park_factors.csv` | As-is |
| `data/mlb_re24_baseline.csv` | `data/mlb_re24_baseline.csv` | As-is |

### Frontend
| Source path | Destination | Notes |
|-------------|-------------|-------|
| `frontend/src/lib/matchupPredictor.ts` | `frontend/src/lib/matchupPredictor.ts` | As-is |
| `frontend/src/components/matchup/*` | `frontend/src/components/matchup/*` | As-is |
| `frontend/src/components/ui/*` | `frontend/src/components/ui/*` | As-is |
| `frontend/src/pages/*.tsx` (all 6) | `frontend/src/pages/*.tsx` | As-is |
| `frontend/src/types/*.ts` | `frontend/src/types/*.ts` | As-is |
| `frontend/src/hooks/useElo.ts` | `frontend/src/hooks/useElo.ts` | Modify: swap Supabase → apiClient |
| `frontend/src/hooks/useMatchup.ts` | `frontend/src/hooks/useMatchup.ts` | Modify: swap Supabase → apiClient |
| `frontend/src/hooks/useTalent.ts` | `frontend/src/hooks/useTalent.ts` | Modify: swap Supabase → apiClient |
| `frontend/src/api/elo.ts` | `frontend/src/api/elo.ts` | Rewrite: call FastAPI instead of Supabase |
| `frontend/src/api/matchup.ts` | `frontend/src/api/matchup.ts` | Rewrite: call FastAPI instead of Supabase |
| `frontend/src/api/talent.ts` | `frontend/src/api/talent.ts` | Rewrite: call FastAPI instead of Supabase |

### SQL Migrations
| Source path | Destination | Notes |
|-------------|-------------|-------|
| `scripts/migrations/*.sql` | `scripts/migrations/*.sql` | Copy all existing |

---

## All Dependencies

### Python (`requirements.txt`)

```
# === Existing (copied from mlb-elo-demo-2025) ===
pandas>=2.0
numpy>=1.24
supabase>=2.0                # Supabase Python client
python-dotenv>=1.0           # .env loading
pybaseball>=2.3              # Fangraphs stats + Statcast data
pyarrow>=14.0                # Parquet file support

# === New for this project ===
fastapi>=0.115               # Unified API backend
uvicorn[standard]>=0.34      # ASGI server
httpx>=0.27                  # Async HTTP client (MLB Stats API)
rapidfuzz>=3.0               # Fuzzy player name matching
reportlab>=4.0               # PDF report generation
pydantic>=2.0                # Request/response models (ships with FastAPI)
python-multipart>=0.0.9      # File upload support in FastAPI
```

### Frontend (`package.json`)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "@tanstack/react-query": "^5.0.0",
    "lightweight-charts": "^4.0.0"
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "typescript": "^5.5.0",
    "@vitejs/plugin-react": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0"
  }
}
```

**Removed from existing**: `@supabase/supabase-js` — frontend no longer talks to Supabase directly.

### System Requirements
- Python 3.11+
- Node.js 20+
- npm 10+

---

## Supabase Setup

**New Supabase project** (or reuse existing — your choice). Tables needed:

### Copied from existing (via migrations 001-005)
- `players` — 1,469 player metadata rows
- `plate_appearances` — 183,092 PAs
- `player_elo` — current composite ELO per player
- `elo_pa_detail` — per-PA ELO deltas
- `talent_player_current` — 9D talent ELO per player
- `talent_pa_details` — per-PA talent deltas
- `daily_ohlc` — 69,125 OHLC candlestick rows

### New table (migration 006)
```sql
-- 006_team_elo.sql
CREATE TABLE team_elo (
    id BIGSERIAL PRIMARY KEY,
    team_code TEXT NOT NULL,
    game_date DATE NOT NULL,
    elo_before FLOAT NOT NULL,
    elo_after FLOAT NOT NULL,
    opponent_code TEXT NOT NULL,
    result TEXT NOT NULL,          -- 'W' or 'L'
    run_diff INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_code, game_date, opponent_code)
);

CREATE INDEX idx_team_elo_team_date ON team_elo(team_code, game_date DESC);
CREATE INDEX idx_team_elo_date ON team_elo(game_date DESC);
```

---

## API Endpoints

### ELO Endpoints (ported from existing frontend Supabase queries)
| Endpoint | Method | Source |
|----------|--------|--------|
| `GET /api/elo/hot-players?date=` | GET | `elo.ts:getHotPlayers()` |
| `GET /api/elo/cold-players?date=` | GET | `elo.ts:getColdPlayers()` |
| `GET /api/elo/leaderboard?position=&page=&limit=` | GET | `elo.ts:getLeaderboard()` |
| `GET /api/elo/players/{id}` | GET | `elo.ts:getPlayerElo()` |
| `GET /api/elo/players/{id}/ohlc?role=` | GET | `elo.ts:getPlayerOhlc()` |
| `GET /api/elo/players/{id}/stats?role=` | GET | `elo.ts:getPlayerStats()` |
| `GET /api/elo/search?q=` | GET | `elo.ts:searchPlayers()` |
| `GET /api/elo/league-summary` | GET | `elo.ts:getLeagueSummary()` |
| `GET /api/elo/latest-date` | GET | `elo.ts:getLatestDate()` |
| `GET /api/elo/season-meta` | GET | `elo.ts:getSeasonMeta()` |

### Talent Endpoints
| Endpoint | Method | Source |
|----------|--------|--------|
| `GET /api/talent/players/{id}/radar` | GET | `talent.ts:getPlayerTalentRadar()` |
| `GET /api/talent/leaderboard?type=&role=&page=&limit=` | GET | `talent.ts:getTalentLeaderboard()` |

### Matchup Endpoints
| Endpoint | Method | Source |
|----------|--------|--------|
| `GET /api/matchup/batter/{id}/talent` | GET | `matchup.ts:getBatterTalentElo()` |
| `GET /api/matchup/pitcher/{id}/talent` | GET | `matchup.ts:getPitcherTalentElo()` |
| `GET /api/matchup/predict/{batterId}/{pitcherId}` | GET | Server-side prediction |

### Fantasy Endpoints (all new)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/fantasy/roster` | POST | Parse pasted roster text, fuzzy-match to DB |
| `GET /api/fantasy/schedule?week=` | GET | MLB probable pitchers for given week |
| `POST /api/fantasy/weekly-projection` | POST | Full weekly projection (roster + week → grid) |
| `GET /api/fantasy/matchup/{batterId}/{pitcherId}` | GET | Single matchup with fantasy points |
| `GET /api/fantasy/team-elo/{teamCode}` | GET | Team ELO current + trend |
| `GET /api/fantasy/team-elo/all` | GET | All 30 team ELOs |
| `POST /api/fantasy/export/pdf` | POST | Generate PDF, return download |

---

## Implementation Phases

### Phase 0: Project Setup + FastAPI Skeleton
1. Create project directory and initialize git
2. Copy all files listed in "Files to Copy" section
3. Create `requirements.txt`, install dependencies
4. Create `src/api/main.py` — FastAPI app with CORS
5. Create `src/api/deps.py` — Supabase client singleton
6. Create `src/api/routers/elo.py` — port all ELO queries from `frontend/src/api/elo.ts`
7. Create `src/api/routers/talent.py` — port talent queries
8. Create `src/api/routers/matchup.py` — port matchup queries
9. Test: all ELO/talent/matchup endpoints return correct data
10. Create `frontend/src/lib/apiClient.ts` — fetch wrapper
11. Rewrite `frontend/src/api/elo.ts`, `talent.ts`, `matchup.ts` to use apiClient
12. Add Vite proxy config (`/api` → `localhost:8000`)
13. Verify: all 6 existing pages work through FastAPI

### Phase 1: Team ELO Engine
1. TDD: write `tests/test_team_elo_engine.py`
2. Implement `src/engine/team_elo_engine.py` (K=4, home +24, MOV multiplier)
3. Create migration `006_team_elo.sql`, apply to Supabase
4. Write `scripts/backfill_team_elo.py`, run against 2025 data
5. Add team ELO endpoints to `src/api/routers/fantasy.py`

### Phase 2: Fantasy Backend Modules
Each follows TDD — write test first.

1. **`matchup_predictor.py`** — port `matchupPredictor.ts` to Python. Cross-validate output.
2. **`roster_parser.py`** — parse pasted text, fuzzy-match via `rapidfuzz`
3. **`schedule_fetcher.py`** — MLB Stats API client, TBD pitcher fallback
4. **`opponent_resolver.py`** — roster × schedule → matchup tuples
5. **`elo_lookup.py`** — batch Supabase queries, in-memory cache
6. **`fangraphs_enricher.py`** — pybaseball wrapper, `.cache/` daily file cache
7. **`fantasy_calculator.py`** — probabilities → ESPN points (TB, BB, SO, R, RBI, SB, IP, K, W, SV, HD, ER)
8. **`weekly_projection.py`** — orchestrator combining all modules
9. Wire up `src/api/routers/fantasy.py` endpoints

### Phase 3: Fantasy Frontend
1. Create `frontend/src/types/fantasy.ts`
2. Create `frontend/src/api/fantasy.ts` — API client
3. Create `frontend/src/hooks/useFantasy.ts` — React Query hooks
4. Build components: `RosterUpload`, `WeekSelector`, `WeeklyGrid`, `PitcherGrid`, `FantasyPointsPanel`, `TeamEloBadge`, `FangraphsSidebar`
5. Build pages: `FantasyDashboard`, `BatterMatchups`, `PitcherMatchups`, `FantasyMatchupDetail`
6. Update `App.tsx` routing + navigation

### Phase 4: PDF Export + Daily Pipeline
1. `src/fantasy/report.py` — reportlab PDF generation
2. `src/api/routers/export.py` — PDF endpoint
3. `ExportPage.tsx` — trigger + download UI
4. `scripts/run_daily.py` — 5-step orchestrator
5. `.github/workflows/daily_update.yml` — cron at 8am EST + manual dispatch

---

## ESPN Scoring Reference

```yaml
batter:
  TB:  +1    # 1B=1, 2B=2, 3B=3, HR=4
  R:   +1
  RBI: +1
  BB:  +1
  SB:  +1
  SO:  -1

pitcher:
  IP:  +3    # per full inning
  K:   +1
  W:   +2
  SV:  +5
  HD:  +2
  H:   -1
  ER:  -2
  BB:  -1
  L:   -2
```

---

## Daily Pipeline (GitHub Actions)

| Step | Script | Action |
|------|--------|--------|
| 1 | `scripts/daily_elo.py --date yesterday` | Update player ELO |
| 2 | `scripts/backfill_team_elo.py --date yesterday` | Update team ELO |
| 3 | `src/fantasy/schedule_fetcher.py --week current` | Refresh probable pitchers |
| 4 | `src/fantasy/fangraphs_enricher.py --refresh` | Pull latest season rates |
| 5 | `scripts/run_weekly.py --regenerate` | Recompute projections |

Cron: `0 13 * * *` (13:00 UTC = 8:00 AM EST)
All steps idempotent (upsert, overwrite, cache-skip).

---

## Verification

### After Phase 0
- `uvicorn src.api.main:app --reload` + `cd frontend && npm run dev`
- All 6 original ELO pages load through FastAPI
- No direct Supabase calls from frontend

### After Phase 1
- `team_elo` table has 2025 data for all 30 teams
- `GET /api/fantasy/team-elo/all` returns ratings

### After Phase 2
- `POST /api/fantasy/roster` resolves sample roster
- `POST /api/fantasy/weekly-projection` returns full weekly grid
- Python matchup predictor matches TS output within 1e-6

### After Phase 3
- `/fantasy` page: upload roster → see projections
- Batter/pitcher grids render correctly
- Matchup detail shows fantasy points breakdown

### After Phase 4
- PDF downloads from `/fantasy/export`
- `python scripts/run_daily.py` completes all steps
- GitHub Actions workflow succeeds
