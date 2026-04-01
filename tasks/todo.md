# Phase 1: Team ELO Engine

## Tasks
- [x] Create team ELO config (`config/team_elo_config.yaml`)
- [x] Write TDD tests (`tests/test_team_elo_engine.py`) — 20/20 passing
- [x] Implement engine (`src/engine/team_elo_engine.py`)
- [x] Create migration (`scripts/migrations/006_team_elo.sql`)
- [x] Create backfill script (`scripts/backfill_team_elo.py`)
- [x] Create API endpoints (`src/api/routers/fantasy.py`)
- [x] Apply all migrations (001-006) to Supabase
- [x] Load 2025 season data through 2025-09-28 (183,092 PAs)
- [x] Backfill team ELO (30 teams, ~2,430 game records)
- [x] Verify API endpoints

## Review
- 183,092 plate appearances loaded
- 1,469 players with ELO ratings
- 30 teams with ELO: NYY #1 (1561), COL #30 (1353)
- Both API endpoints returning correct data
- Bulk loader (`scripts/bulk_load.py`) reduced load time from 60+ min to ~90 seconds

---

# Phase 2: Fantasy Backend Modules

## Tasks
- [x] Port matchup_predictor.py from TypeScript (TDD, cross-validate) — 24/24 tests
- [x] roster_parser.py — parse pasted roster text, fuzzy-match names — 11/11 tests
- [x] schedule_fetcher.py — MLB Stats API for probable pitchers — 9/9 tests
- [x] opponent_resolver.py — roster × schedule → matchup tuples — 7/7 tests
- [x] elo_lookup.py — batch Supabase queries, in-memory cache — 7/7 tests
- [x] fangraphs_enricher.py — pybaseball wrapper with daily cache — 14/14 tests
- [x] fantasy_calculator.py — probabilities → ESPN fantasy points — 12/12 tests
- [x] weekly_projection.py — orchestrator combining all modules — 8/8 tests
- [x] Wire up src/api/routers/fantasy.py endpoints + matchup predict endpoint

## Review
- 112/112 tests passing across all modules
- 8 fantasy modules in src/fantasy/ (all complete)
- 5 new API endpoints: POST /roster, GET /schedule, POST /weekly-projection, GET /matchup/{b}/{p}, GET /predict/{b}/{p}
- Matchup predictor cross-validated against TypeScript (identical constants and logic)
- Fangraphs enricher: daily parquet cache in .cache/, auto-cleanup of stale files

---

# Phase 3: Fantasy Frontend

## Tasks
- [x] Create types/fantasy.ts — TypeScript interfaces for all API responses
- [x] Create api/fantasy.ts — API client functions via apiClient
- [x] Create hooks/useFantasy.ts — React Query hooks (useQuery + useMutation)
- [x] Create TeamEloBadge component — inline hot/cold team indicator
- [x] Create FantasyPointsPanel component — total/batter/pitcher summary cards
- [x] Create WeekSelector component — Mon-Sun week picker with prev/next
- [x] Create RosterUpload component — paste area + parse + results table
- [x] Create WeeklyGrid component — batter matchup table (rows × days)
- [x] Create PitcherGrid component — pitcher start projections table
- [x] Create FangraphsSidebar component — wRC+/ERA- context display
- [x] Create FantasyDashboard page — roster upload → week summary
- [x] Create BatterMatchups page — full weekly batter grid
- [x] Create PitcherMatchups page — pitcher projection view
- [x] Create FantasyMatchupDetail page — single matchup deep dive
- [x] Add routes to App.tsx (/fantasy, /fantasy/batters, /fantasy/pitchers, /fantasy/matchup/:b/:p)
- [x] Add "Fantasy" nav link to Header.tsx

## Review
- 14 new frontend files created (types, api, hooks, 7 components, 4 pages)
- 2 existing files modified (App.tsx, Header.tsx)
- Backend tests still 112/112 passing
- Node.js not available in environment — TS type check deferred to user verification

---

# Phase 4: PDF Export + Daily Pipeline

## Tasks
- [x] Create `src/fantasy/report.py` — reportlab PDF generation
- [x] Create `src/api/routers/export.py` — POST /api/fantasy/export/pdf endpoint
- [x] Modify `src/api/main.py` — register export router
- [x] Create `scripts/run_daily.py` — 5-step daily orchestrator
- [x] Create `scripts/run_weekly.py` — weekly Fangraphs cache refresh
- [x] Create `frontend/src/pages/ExportPage.tsx` — PDF trigger + download UI
- [x] Modify `frontend/src/App.tsx` — add /export route
- [x] Create `.github/workflows/daily_update.yml` — cron at 8am EST
- [x] Run tests to verify no regressions — 112/112 passing

## Review
- 6 new files created, 2 existing files modified
- PDF generation tested: valid PDF with title, summary, batter/pitcher tables, team ELO rankings
- Export endpoint: POST /api/fantasy/export/pdf → StreamingResponse with downloadable PDF
- Daily pipeline: 4-step orchestrator (player ELO, team ELO, Fangraphs cache, schedule fetch)
- Weekly script: refreshes Fangraphs batting + pitching stat caches
- GitHub Actions: daily cron at 8am EST + manual dispatch with optional date input
- All 112 backend tests still passing
