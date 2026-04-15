-- Add hits, home_runs (batters) and bf (pitchers) to player_season_stats.
-- v2 of the table — all new columns default to 0 so existing rows are unaffected.

ALTER TABLE player_season_stats
  ADD COLUMN IF NOT EXISTS hits       INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS home_runs  INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS bf         INT NOT NULL DEFAULT 0;
