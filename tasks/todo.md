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
