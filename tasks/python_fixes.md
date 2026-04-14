# Python Code Improvement Backlog

## Critical

- [ ] **`tests/test_fangraphs_enricher.py`** — Imports removed names (`BATTER_COLS`, `PITCHER_COLS`, `batting_stats`, `pitching_stats`); every test fails with `ImportError`. Rewrite to match current `get_pitcher_stats`/`get_player_stats` interface.

---

## High

- [ ] **`src/pipeline/daily_pipeline.py:437,473`** — `_detect_season_boundary` called twice, two DB round-trips for identical result. Store once: `is_new_season = _detect_season_boundary(client, target_date)`.
- [ ] **`src/fantasy/weekly_projection.py:432`** — `weekly_appearances` only assigned inside `if rp_slots:` but referenced unconditionally. Initialize to `0` before the block.
- [ ] **`scripts/validate_etl.py:6`** — Hardcoded absolute path to `/Users/mksong/...`. Script is non-functional. Delete or accept path via `argparse`.
- [ ] **`scripts/run_elo.py:64–102` + `src/pipeline/daily_pipeline.py:333–368`** — `_prepare_pa_detail_records` and `_prepare_ohlc_records` are near-duplicates. Move to `src/etl/upload_to_supabase.py` with an optional param for extra ELO fields.

---

## Medium

- [ ] **Paginated Supabase fetch (10+ files)** — Identical `while True: .range().execute()` pattern duplicated everywhere. Extract to `fetch_all(query, page_size=1000)` in `upload_to_supabase.py`. Affected: `daily_pipeline.py`, `run_elo.py`, `derive_re24_baseline.py`, `backfill_team_elo.py`, `compute_matchup_constants.py`, `seed_speed_elo_fg.py`, `elo.py`, `fantasy.py`, `fangraphs_enricher.py`.
- [ ] **`scripts/seed_speed_elo_fg.py:134–140`** — Manually constructs Supabase client instead of calling `get_supabase_client()`.
- [ ] **`scripts/compute_matchup_constants.py:14–18`** — Same manual Supabase client construction; use `get_supabase_client()`.
- [ ] **`scripts/seed_speed_elo_fg.py:34–37`** — Redefines `ELO_BASE/MIN/MAX` already in `src/engine/multi_elo_types.py`. Import from there instead.
- [ ] **`src/api/routers/fantasy.py:295–315`** — `daily_projection` endpoint is a near-copy of `weekly_projection` with one filter line different. Refactor into a shared helper.
- [ ] **`src/pipeline/daily_pipeline.py:371–512`** — `run_daily_pipeline` is 140 lines handling 9+ distinct steps. Extract `_upload_elo_results` and `_upload_talent_results`.
- [ ] **`scripts/compute_matchup_constants.py`** — All logic executes at import time; no `if __name__ == '__main__'` guard. Wrap in `def main()`.
- [ ] **`src/api/routers/elo.py:337–391`** — `_daily_fantasy` fetches ~5000 rows into Python and aggregates manually. Move to a DB aggregate query or Supabase RPC.
- [ ] **`scripts/derive_re24_baseline.py:93–97`** — `encode_base_out_state` applied row-by-row with `axis=1`. Vectorize with bitwise logic on base/out columns.
- [ ] **`src/etl/statcast_to_pa.py:65`** — `_get_runner_id` applied row-by-row. Replace with `np.select` on event type conditions.
- [ ] **`src/etl/player_lookup.py`** — Entirely dead module (MongoDB references, zero imports anywhere). Delete.
- [ ] **`src/engine/elo_batch.py:244–247`** — O(n×m) scan to find last game date per player. Pre-build a `{player_id: max_date}` dict once before the loop.

---

## Low

- [ ] **`scripts/run_elo.py:122–128`** — Manual variance calculation; replace with `np.mean`/`np.std`.
- [ ] **`scripts/run_weekly.py:38–41`** — Calls `get_batter_stats` which returns `pd.DataFrame()`. Remove the dead call and the stub export.
- [ ] **`src/fantasy/weekly_projection.py:255`** — `iterrows()` to build a name→row dict. Use `set_index("Name").to_dict("index")` instead.
- [ ] **`scripts/run_elo.py:14`, `scripts/bulk_load.py:13`** — Unused `import math`. Remove.
- [ ] **`src/engine/elo_batch.py:55`** — `k_factor: float = None` should be `k_factor: float | None = None`.
- [ ] **`src/pipeline/daily_pipeline.py:371`** — `target_date: date = None` should be `target_date: date | None = None`.
- [ ] **`src/etl/upload_to_supabase.py:48`** — `client` param and `get_supabase_client` return value are untyped. Annotate with `supabase.Client`.
- [ ] **`scripts/backfill_team_elo.py:40`** — `fetch_pa_rows` missing return type `-> list[dict]`.
- [ ] **`src/fantasy/weekly_projection.py:27–43,396`** — Projection constants (`AVG_PA_PER_GAME`, `BASE_WIN_PROB`, `SEASON_GAMES`, etc.) scattered inline or inside loops. Move to config yaml.
- [ ] **`scripts/bulk_load.py:53–57`** — Hardcoded season start dates dict. Move to `config/seasons.yaml`.
- [ ] **`src/fantasy/fantasy_calculator.py:13–20`** — `SPEED_ELO_MEAN`, `SPEED_ELO_STD`, `MLB_AVG_SB_PER_GAME` magic numbers. Move to config yaml.
