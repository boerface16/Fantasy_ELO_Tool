-- Phase 8: 9-Dimensional Talent ELO Schema
-- 3 new tables: talent_player_current, talent_pa_detail, talent_daily_ohlc

-- 1. Talent Player Current (per player × dimension snapshot)
CREATE TABLE IF NOT EXISTS talent_player_current (
  player_id      INTEGER NOT NULL REFERENCES players(player_id),
  player_role    VARCHAR(10) NOT NULL,  -- 'batter' or 'pitcher'
  talent_type    VARCHAR(20) NOT NULL,  -- dimension name
  season_elo     REAL DEFAULT 1500.0,
  career_elo     REAL DEFAULT 1500.0,
  event_count    INTEGER DEFAULT 0,
  pa_count       INTEGER DEFAULT 0,
  PRIMARY KEY (player_id, talent_type, player_role)
);
CREATE INDEX IF NOT EXISTS idx_talent_current_type ON talent_player_current(talent_type);
CREATE INDEX IF NOT EXISTS idx_talent_current_role ON talent_player_current(player_role);

-- 2. Talent PA Detail (per PA × player × dimension)
CREATE TABLE IF NOT EXISTS talent_pa_detail (
  id             SERIAL PRIMARY KEY,
  pa_id          BIGINT NOT NULL REFERENCES plate_appearances(pa_id),
  player_id      INTEGER NOT NULL,
  player_role    VARCHAR(10) NOT NULL,
  talent_type    VARCHAR(20) NOT NULL,
  elo_before     REAL NOT NULL,
  elo_after      REAL NOT NULL,
  delta          REAL GENERATED ALWAYS AS (elo_after - elo_before) STORED,
  UNIQUE (pa_id, player_id, talent_type)
);
CREATE INDEX IF NOT EXISTS idx_talent_pa_player ON talent_pa_detail(player_id, talent_type);
CREATE INDEX IF NOT EXISTS idx_talent_pa_date ON talent_pa_detail(pa_id);

-- 3. Talent Daily OHLC (per player × dimension × date)
CREATE TABLE IF NOT EXISTS talent_daily_ohlc (
  id             SERIAL PRIMARY KEY,
  player_id      INTEGER NOT NULL REFERENCES players(player_id),
  game_date      DATE NOT NULL,
  talent_type    VARCHAR(20) NOT NULL,
  elo_type       VARCHAR(10) NOT NULL DEFAULT 'SEASON',
  open_elo       REAL NOT NULL,
  high_elo       REAL NOT NULL,
  low_elo        REAL NOT NULL,
  close_elo      REAL NOT NULL,
  delta          REAL GENERATED ALWAYS AS (close_elo - open_elo) STORED,
  elo_range      REAL GENERATED ALWAYS AS (high_elo - low_elo) STORED,
  total_pa       INTEGER DEFAULT 0,
  UNIQUE (player_id, game_date, talent_type, elo_type)
);
CREATE INDEX IF NOT EXISTS idx_talent_ohlc_player ON talent_daily_ohlc(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_talent_ohlc_type ON talent_daily_ohlc(talent_type, game_date);
CREATE INDEX IF NOT EXISTS idx_talent_ohlc_delta ON talent_daily_ohlc(game_date, talent_type, delta DESC);
