-- Player season-level stats table for exact ESPN fantasy point calculation.
-- Sourced from MLB Stats API (player IDs match our players.player_id).
--
-- Run in Supabase SQL Editor or: psql $DATABASE_URL -f scripts/migrations/009_player_season_stats.sql

CREATE TABLE IF NOT EXISTS player_season_stats (
  player_id      INTEGER NOT NULL REFERENCES players(player_id),
  season_year    INTEGER NOT NULL,
  -- batting
  pa             INTEGER NOT NULL DEFAULT 0,
  total_bases    INTEGER NOT NULL DEFAULT 0,
  runs           INTEGER NOT NULL DEFAULT 0,
  rbi            INTEGER NOT NULL DEFAULT 0,
  sb             INTEGER NOT NULL DEFAULT 0,
  bb             INTEGER NOT NULL DEFAULT 0,
  hbp            INTEGER NOT NULL DEFAULT 0,
  so             INTEGER NOT NULL DEFAULT 0,
  -- pitching (outs_recorded = floor(IP) * 3 + partial outs)
  outs_recorded  INTEGER NOT NULL DEFAULT 0,
  k              INTEGER NOT NULL DEFAULT 0,
  wins           INTEGER NOT NULL DEFAULT 0,
  losses         INTEGER NOT NULL DEFAULT 0,
  saves          INTEGER NOT NULL DEFAULT 0,
  holds          INTEGER NOT NULL DEFAULT 0,
  h_allowed      INTEGER NOT NULL DEFAULT 0,
  er             INTEGER NOT NULL DEFAULT 0,
  bb_allowed     INTEGER NOT NULL DEFAULT 0,
  hbp_allowed    INTEGER NOT NULL DEFAULT 0,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (player_id, season_year)
);

CREATE INDEX IF NOT EXISTS idx_player_season_stats_year
  ON player_season_stats(season_year);
