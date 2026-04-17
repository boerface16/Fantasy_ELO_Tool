# Lessons Learned

## Data Loading
- **Supabase REST API timeouts on bulk uploads**: Free-tier Supabase has statement timeout limits. Use psycopg2 `execute_values` via the pooler DATABASE_URL for bulk operations (>1000 rows). Keep REST API for daily incremental loads (batch_size=500).
- **DATABASE_URL password with special chars**: Password `YjnZa_A$t266@CY` contains `@`. Use `rsplit('@', 1)` to split on the *last* `@` when parsing the URL.
- **numpy int64 not JSON-serializable**: Always cast `int(pid)` before passing player IDs to JSON-based APIs (Supabase REST, requests).
- **Generated columns in Supabase**: Cannot INSERT non-DEFAULT values into generated columns (e.g. `delta` in `talent_pa_detail`). Exclude them from upload dicts.
- **Column name mismatches**: DB columns `open_elo/high_elo/low_elo/close_elo` vs code using `open/high/low/close`. Always verify column names against the migration SQL.
- **Supabase pagination default limit**: Supabase REST returns at most 1000 rows per request. Always paginate with `.range(offset, offset+999)` in a loop when fetching full tables or large result sets (e.g. distinct game dates from plate_appearances).

## Speed ELO
- **Statcast pitch data omits SB/CS/PKO rows entirely**: pybaseball Statcast returns 0 SB/CS/PKO event rows — confirmed by live test on 2026-03-25 which had a stolen base. Never build speed ELO from Statcast baserunning events. Use MLB API box scores (`/game/{game_pk}/boxscore`) as the authoritative source for SB/CS per game.
- **MLB API schedule+boxscore hydration does not work**: `GET /schedule?hydrate=boxscore` returns empty boxscore dicts. Must use two-step: (1) `/schedule` to get game_pks, (2) `/game/{game_pk}/boxscore` for each game.
- **Bulk z-score seed fights event-based ELO**: A daily seed that overwrites `talent_player_current.season_elo` with a season-total z-score destroys all per-event deltas computed that day. If you ever add a new ELO dimension, do not run a bulk overwrite alongside an event-based system. The fix: delete the bulk seed; use `speed_elo_daily.py` (MLB API box scores) after the daily pipeline.
- **FK order for resets**: When deleting plate_appearances rows that are referenced by talent_pa_detail, delete talent_pa_detail rows FIRST, then plate_appearances. Reversing the order causes `violates foreign key constraint` errors.
- **Synthetic pa_id scheme**: MLB API supplement rows use `game_pk * 1_000_000 + 950_000 + seq`. Safe from collision with regular PAs (`game_pk * 1000 + at_bat_number`, max ~60k) and Statcast baserunning PAs (`game_pk * 1_000_000 + at_bat_number*1000 + pitch_number`, max ~60k per game).

## Daily Pipeline

- **Synthetic SB/CS/PKO rows block the idempotency check**: The daily pipeline checks `plate_appearances` row count to decide if a date was already processed. Synthetic rows inserted by the speed ELO backfill count toward that total — causing real Statcast data to never be loaded for dates with stolen base events. Fix: exclude `result_type IN ('SB','CS','PKO')` from the idempotency count.
- **`_detect_season_boundary` fails without prior-year plate_appearances**: The original check compared the most recent `plate_appearances.game_date` year against the target year. On a fresh system (no 2025 data), this always returns False and the season ELO reset never fires — leaving players at seeded/projection ELOs (~1900) instead of a regression-to-mean value. Fix: check `player_elo.last_game_date` first; it's always populated after prior runs.
- **`player_ohlc` without a role filter returns mixed BATTING+PITCHING rows**: The endpoint's `role` param was optional (`None`). When callers omit it, `daily_ohlc` rows for both roles appear on the same chart, creating an anomalous tall candle. Fix: default `role='BATTING'` so a filter is always applied.

## Talent ELO Charts

- **Speed (and all talent) OHLC only has rows on event days**: `talent_daily_ohlc` gets a row only when a speed event (SB/CS/3B/GBS) occurs. Non-event game days produce no row, so the chart has gaps. Fix: in the API, fetch the player's game-day spine from `daily_ohlc` and forward-fill flat candles (`open=high=low=close=last_close`) for days with no talent event.

## Team ELO Engine
- **Doubleheaders need game_pk**: Two games on the same date between the same teams require `game_pk` in the UNIQUE constraint to avoid conflicts.
- **Inning half mapping for scores**: `bat_score`/`fld_score` meaning flips based on `inning_half` — top inning: batting=away, bottom inning: batting=home.
