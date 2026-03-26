# Lessons Learned

## Data Loading
- **Supabase REST API timeouts on bulk uploads**: Free-tier Supabase has statement timeout limits. Use psycopg2 `execute_values` via the pooler DATABASE_URL for bulk operations (>1000 rows). Keep REST API for daily incremental loads (batch_size=500).
- **DATABASE_URL password with special chars**: Password `YjnZa_A$t266@CY` contains `@`. Use `rsplit('@', 1)` to split on the *last* `@` when parsing the URL.
- **numpy int64 not JSON-serializable**: Always cast `int(pid)` before passing player IDs to JSON-based APIs (Supabase REST, requests).
- **Generated columns in Supabase**: Cannot INSERT non-DEFAULT values into generated columns (e.g. `delta` in `talent_pa_detail`). Exclude them from upload dicts.
- **Column name mismatches**: DB columns `open_elo/high_elo/low_elo/close_elo` vs code using `open/high/low/close`. Always verify column names against the migration SQL.

## Team ELO Engine
- **Doubleheaders need game_pk**: Two games on the same date between the same teams require `game_pk` in the UNIQUE constraint to avoid conflicts.
- **Inning half mapping for scores**: `bat_score`/`fld_score` meaning flips based on `inning_half` — top inning: batting=away, bottom inning: batting=home.
