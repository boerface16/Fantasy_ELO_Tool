# Plan: Remove Redundancies & Bloat in src/, scripts/, frontend/

## Context
The fantasy-matchup-predictor codebase has grown through multiple phases (Team ELO, Speed ELO, Fantasy Frontend, Talent ELO). Organic growth has left duplicated logic across backend modules, near-identical orchestration scripts, and parallel frontend components (e.g., `PlayerCard` vs `FantasyPlayerCard`). Exploration found **~400–500 lines of removable duplication** and several likely-dead scripts. Goal: consolidate without regressing behavior, so future phases build on a smaller, clearer surface.

Verification done during exploration:
- `daily_elo.py` has zero code references (only itself + docs).
- `backfill_speed_elo.py` and `derive_re24_baseline.py` referenced only in docs, not in `run_daily.py` / `run_weekly.py` / `src/pipeline/`.
- `TeamLogo.tsx` IS used by `PlayerProfile.tsx` — keep.
- `AdBanner.tsx` IS used by `Layout.tsx` — keep.

## Approach: Three Phases, Behavior-Preserving

Each phase ends with tests + a targeted end-to-end run. Do phases in order; don't bundle.

---

### Phase A — Backend (`src/`) Consolidation

**A1. Unify fantasy points calculation** (high impact, ~120 lines)
- Create `src/fantasy/scoring.py` with a single `compute_fantasy_points(stats, role, scoring_cfg)` that handles both *actual* (counting stats) and *estimated* (rate-based) modes via a `mode` param.
- Delete `_batter_pts`, `_batter_pts_actual`, `_pitcher_pts`, `_pitcher_pts_actual` from `src/api/routers/elo.py` (lines 99–213).
- Reuse existing `src/fantasy/fantasy_calculator.py` functions where they match; move them into `scoring.py` and re-export.
- Cache `_load_scoring()` YAML read at module-level (currently reloads per request, `elo.py:169-173`).

**A2. Shared ELO math utilities** (medium impact, ~80 lines)
- New file: `src/engine/elo_utils.py` with:
  - `expected_score(player, opp, divisor)` — replaces duplicated logistic in `multi_elo_engine.py:55-59` and `team_elo_engine.py:68-69`.
  - `season_reset(prior, projection, weight_projection=0.67)` — replaces duplicated 538 reset in `elo_calculator.py:66-96` and `team_elo_engine.py:74-104`.
- Update both callers to import from `elo_utils`.

**A3. Extract OHLC helper** (medium impact, ~50 lines)
- New file: `src/engine/ohlc_tracker.py` with `OHLCTracker` class wrapping `_record_ohlc_open`, `_update_ohlc`, `_finalize_day`.
- Replace duplicated logic in `elo_batch.py:69-100` and `talent_batch.py:49-72`.

**A4. Split bloated `elo.py` router** (medium impact, quality)
- `src/api/routers/elo.py` is 796 lines. Extract:
  - MLB Stats API wrappers (`_fetch_batter_game_log`, `_fetch_pitcher_game_log`) → `src/api/services/mlb_stats.py`
  - Flatten helpers (`_flatten_ohlc_player`, `_flatten_leaderboard`) → `src/api/services/formatters.py`
- Router keeps only endpoint handlers. Target: <300 lines.

---

### Phase B — Scripts Consolidation

**B1. Delete / archive dead scripts** (high impact, removes ~700 lines)
- **Delete** `scripts/daily_elo.py` — fully superseded by `run_daily.py --date X`.
- **Archive** (move to `scripts/archive/`) with a README explaining when to re-run:
  - `scripts/backfill_speed_elo.py` (superseded by incremental `speed_elo_daily`)
  - `scripts/derive_re24_baseline.py` (one-time baseline generator)
  - `scripts/run_elo.py` (one-shot full-season rebuild; overlaps with `bulk_load.py`)
- Before archiving `backfill_speed_elo.py`, confirm `src/pipeline/speed_elo_daily.py` covers its logic.

**B2. Shared script bootstrap** (high impact, touches 14 files)
- New `scripts/_common.py`:
  ```python
  def init_script_env():
      load_dotenv(...); sys.path.insert(...); logging.basicConfig(...)
  ```
- Replace the 3-line boilerplate in every script's header with `from _common import init_script_env; init_script_env()`.

**B3. Standardize Supabase client** (high impact)
- All 7 scripts with custom `get_supabase()` must import `get_supabase_client` from `src/etl/upload_to_supabase.py`.
- Delete inline `create_client(...)` definitions in: `backfill_speed_elo.py:41-42`, `backtest.py:28`, `repair_player_teams.py:29-30`, `export_speed_elo.py:29-30`, `verify_fantasy_points.py:31-34`.

**B4. Move ESPN creds & season to config** (high impact, security hygiene)
- Hardcoded `league_id=30294024`, `espn_s2`, `swid` in `ESPN_API.py:4-10` and `pull_current_fantasy_bits.py:14-18`.
- Move to `.env`: `ESPN_LEAGUE_ID`, `ESPN_S2`, `ESPN_SWID`, `DEFAULT_SEASON`.
- Hardcoded `SEASON=2026` in `verify_fantasy_points.py:25` → env var.
- Hardcoded `SEASON_STARTS` dict in `bulk_load.py:53-60` → `config/game_config.yaml`.

**B5. Shared pagination helper** (medium impact)
- New `src/etl/pagination.py` with `paginate(client, table, select, page_size=1000)` generator.
- Replace copy-pasted while-loops in `backfill_speed_elo.py:104-119`, `repair_player_teams.py:69-77`, `bulk_load.py:73-97`, `compute_matchup_constants.py:29-39`.

**B6. Clean `ESPN_API.py`** (low impact)
- Lines 43+ are demo/tutorial code, not imported anywhere. Delete or move to `scripts/archive/examples/`.

---

### Phase C — Frontend Consolidation

**C1. Extract wOBA color utility** (high impact, easy win)
- New `frontend/src/utils/wobaColors.ts` exporting `getWobaBg(woba)` and `getWobaAgainstBg(woba)`.
- Delete duplicate `wobaColor` functions in `DailyGrid.tsx:8`, `WeeklyGrid.tsx:21`, `PitcherGrid.tsx:7`.

**C2. Merge PlayerCard variants** (high impact, ~100 lines)
- Create `frontend/src/components/dashboard/BasePlayerCard.tsx` accepting `{ headerValue, headerFormatter, playerName, team, role }`.
- Refactor `PlayerCard.tsx` and `FantasyPlayerCard.tsx` to thin wrappers passing different formatters (delta vs fantasy_points).

**C3. Merge HotColdSection variants** (high impact, ~80 lines)
- Create generic `HotColdSection<T>` component taking `{ useHotQuery, useColdQuery, CardComponent, roles }` as props.
- Delete or collapse `HotColdSection.tsx` + `FantasyHotColdSection.tsx` into this.

**C4. Generic leaderboard table** (medium impact, ~150 lines)
- New `frontend/src/components/common/LeaderboardTable.tsx` with `columns: ColumnConfig[]` and `renderRow` prop.
- Refactor `LeaderboardTable.tsx`, `FantasyLeaderboardTable.tsx`, `TalentLeaderboardTable.tsx` to use it.

**C5. Date utilities** (low impact)
- New `frontend/src/utils/dateUtils.ts` with `toDateString(d)` and `getWeekDates(start)`.
- Replace scattered `.toISOString().split('T')[0]` in `DatePicker.tsx`, `WeeklyGrid.tsx`, `EloCandlestickChart.tsx`, `ExportPage.tsx`, `FantasyDashboard.tsx`.

**C6. Skip — do NOT do now**
- Hook factory for `useElo`/`useFantasy`/`useMatchup`/`useTalent` — hooks may legitimately diverge; verbosity is fine.
- `BatterMatchup`/`PitcherMatchup` type merge — they may diverge; minimal duplication.
- `TeamLogo.tsx`, `AdBanner.tsx` — verified as used, keep.

---

## Critical Files to Modify

**Backend:**
- `src/api/routers/elo.py` (split + dedup)
- `src/fantasy/fantasy_calculator.py` → `src/fantasy/scoring.py`
- `src/engine/elo_calculator.py`, `multi_elo_engine.py`, `team_elo_engine.py` (import shared utils)
- `src/engine/elo_batch.py`, `talent_batch.py` (use OHLCTracker)
- NEW: `src/engine/elo_utils.py`, `src/engine/ohlc_tracker.py`, `src/etl/pagination.py`

**Scripts:**
- NEW: `scripts/_common.py`, `scripts/archive/` (with README)
- DELETE: `scripts/daily_elo.py`
- MOVE to archive: `backfill_speed_elo.py`, `derive_re24_baseline.py`, `run_elo.py`
- EDIT: all remaining 11 scripts (swap to `_common` + `get_supabase_client`)
- EDIT: `ESPN_API.py`, `pull_current_fantasy_bits.py`, `verify_fantasy_points.py`, `bulk_load.py` (config values)

**Frontend:**
- NEW: `frontend/src/utils/wobaColors.ts`, `utils/dateUtils.ts`, `components/common/LeaderboardTable.tsx`, `components/dashboard/BasePlayerCard.tsx`
- EDIT: `DailyGrid.tsx`, `WeeklyGrid.tsx`, `PitcherGrid.tsx`, `PlayerCard.tsx`, `FantasyPlayerCard.tsx`, `HotColdSection.tsx`, `FantasyHotColdSection.tsx`, 3 leaderboard tables

---

## Verification

Run after **each phase** — don't bundle.

**After Phase A:**
- `pytest tests/ -x` — full suite must stay green (112+ existing tests cover fantasy/engine).
- Start API: `uvicorn src.api.main:app`; hit `/api/elo/leaderboard`, `/api/elo/hot`, `/api/elo/player/{id}/games` — compare JSON shape vs a pre-refactor snapshot.

**After Phase B:**
- `python scripts/run_daily.py --date 2026-04-16` end-to-end; confirm same row counts written to Supabase as a prior run.
- `python scripts/backfill_team_elo.py --season 2026 --dry-run` still parses args and connects.
- Grep-check: no remaining `create_client(os.environ["SUPABASE_URL"]...)` calls outside `src/etl/upload_to_supabase.py`.

**After Phase C:**
- `cd frontend && npm run build` — clean build, no TS errors.
- `npm run dev` — manually load Dashboard, Fantasy Dashboard, Leaderboard, Player Profile; screenshot-compare cards and tables (wOBA colors unchanged, hot/cold grids render, leaderboards sort).
- `npm run lint` — no new warnings.

---

## Per-CLAUDE.md Workflow Notes
- Write this phase breakdown to `tasks/todo.md` with checkboxes **before** starting Phase A.
- After each phase: add Review section with line-count deltas and test results.
- If any behavioral regression found mid-phase: revert that item, log root cause to `tasks/lessons.md`.
- Do NOT bundle all three phases in one PR — deliver A, B, C as separate commits/PRs so regressions are bisectable.

## Estimated Impact
- **Phase A**: ~250 lines removed, router split into clearer modules
- **Phase B**: ~700 lines removed (archived scripts) + ~200 lines of boilerplate consolidated
- **Phase C**: ~350 lines removed via component consolidation
- **Total: ~1,500 line reduction, no behavior change**
