-- MLB ELO Phase 1: 테이블 생성
-- Supabase Dashboard > SQL Editor에서 실행

-- 1. Players
CREATE TABLE IF NOT EXISTS players (
  player_id      INTEGER PRIMARY KEY,
  first_name     VARCHAR(50),
  last_name      VARCHAR(50),
  full_name      VARCHAR(100) NOT NULL,
  team           VARCHAR(50),
  position       VARCHAR(10)
);
CREATE INDEX IF NOT EXISTS idx_players_name ON players(full_name);

-- 2. Plate Appearances
CREATE TABLE IF NOT EXISTS plate_appearances (
  pa_id          BIGINT PRIMARY KEY,
  game_pk        INTEGER NOT NULL,
  game_date      DATE NOT NULL,
  season_year    INTEGER NOT NULL,
  batter_id      INTEGER NOT NULL REFERENCES players(player_id),
  pitcher_id     INTEGER NOT NULL REFERENCES players(player_id),
  result_type    VARCHAR(20) NOT NULL,
  inning         SMALLINT NOT NULL,
  inning_half    VARCHAR(3) NOT NULL,
  at_bat_number  SMALLINT NOT NULL,
  outs_when_up   SMALLINT NOT NULL,
  on_1b          BOOLEAN DEFAULT FALSE,
  on_2b          BOOLEAN DEFAULT FALSE,
  on_3b          BOOLEAN DEFAULT FALSE,
  home_team      VARCHAR(3),
  away_team      VARCHAR(3),
  bat_score      SMALLINT,
  fld_score      SMALLINT,
  launch_speed   REAL,
  launch_angle   REAL,
  xwoba          REAL,
  delta_run_exp  REAL
);
CREATE INDEX IF NOT EXISTS idx_pa_game ON plate_appearances(game_pk);
CREATE INDEX IF NOT EXISTS idx_pa_batter ON plate_appearances(batter_id);
CREATE INDEX IF NOT EXISTS idx_pa_pitcher ON plate_appearances(pitcher_id);
CREATE INDEX IF NOT EXISTS idx_pa_date ON plate_appearances(game_date);

-- 3. Player ELO
CREATE TABLE IF NOT EXISTS player_elo (
  player_id      INTEGER PRIMARY KEY REFERENCES players(player_id),
  player_type    VARCHAR(10),
  on_base_elo    REAL DEFAULT 1500.0,
  power_elo      REAL DEFAULT 1500.0,
  composite_elo  REAL DEFAULT 1500.0,
  pa_count       INTEGER DEFAULT 0,
  last_game_date DATE
);

-- 4. ELO PA Detail
CREATE TABLE IF NOT EXISTS elo_pa_detail (
  pa_id              BIGINT PRIMARY KEY REFERENCES plate_appearances(pa_id),
  batter_id          INTEGER,
  pitcher_id         INTEGER,
  result_type        VARCHAR(20),
  batter_elo_before  REAL,
  batter_elo_after   REAL,
  pitcher_elo_before REAL,
  pitcher_elo_after  REAL,
  on_base_delta      REAL,
  power_delta        REAL
);
CREATE INDEX IF NOT EXISTS idx_elo_detail_batter ON elo_pa_detail(batter_id);
CREATE INDEX IF NOT EXISTS idx_elo_detail_pitcher ON elo_pa_detail(pitcher_id);

-- 5. Daily OHLC
CREATE TABLE IF NOT EXISTS daily_ohlc (
  id             SERIAL PRIMARY KEY,
  player_id      INTEGER NOT NULL REFERENCES players(player_id),
  game_date      DATE NOT NULL,
  elo_type       VARCHAR(10) NOT NULL,
  open           REAL NOT NULL,
  high           REAL NOT NULL,
  low            REAL NOT NULL,
  close          REAL NOT NULL,
  delta          REAL GENERATED ALWAYS AS (close - open) STORED,
  range          REAL GENERATED ALWAYS AS (high - low) STORED,
  games_played   INTEGER DEFAULT 1,
  total_pa       INTEGER DEFAULT 0,
  UNIQUE (player_id, game_date, elo_type)
);
CREATE INDEX IF NOT EXISTS idx_ohlc_player_date ON daily_ohlc(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_ohlc_delta ON daily_ohlc(game_date, elo_type, delta DESC);
