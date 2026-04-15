-- Advanced stats from Statcast (xWOBA) and Fangraphs (WRC+, WAR, xFIP-, SIERA).
-- Fangraphs fields are nullable — they stay NULL if the fetch is rate-limited (403).
-- Populated daily by src/etl/fetch_fangraphs_stats.py.

CREATE TABLE IF NOT EXISTS player_fangraphs_stats (
  player_id   INT  NOT NULL REFERENCES players(player_id),
  season_year INT  NOT NULL,
  xwoba       FLOAT,      -- xwOBA from Baseball Savant (est_woba) — reliable
  wrc_plus    FLOAT,      -- wRC+ from Fangraphs — batters only
  war         FLOAT,      -- WAR from Fangraphs  — batters only
  xfip_minus  FLOAT,      -- xFIP- from Fangraphs — pitchers only
  siera       FLOAT,      -- SIERA from Fangraphs  — pitchers only
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (player_id, season_year)
);

CREATE INDEX IF NOT EXISTS idx_player_fg_stats_year
  ON player_fangraphs_stats(season_year);
