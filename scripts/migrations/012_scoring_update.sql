-- Scoring update migration: add new pitcher stat columns + rewrite leaderboard functions.
--
-- New scoring (espn_scoring.yaml v2):
--   Batter:  TB(+1) R(+1) RBI(+1) BB(+1) SB(+1) SO(-1) E(-3, not in season stats)
--   Pitcher: IP*3(+3/IP) K(+1) H(-1) ER(-1) HR(-1) BB(-1) HB(+1)
--            W(+5) L(-5) SV(+5) BS(-5) CG(+3) SHO(+5) B(-10) PKO(+2)
--            [NH(+10) PG(+11) not tracked in season stats]
--
-- Run: psql $DATABASE_URL -f scripts/migrations/012_scoring_update.sql
--   or paste into Supabase SQL Editor.

-- ── Step 1: Add missing pitcher columns ──────────────────────────────────────

ALTER TABLE player_season_stats
  ADD COLUMN IF NOT EXISTS hr_allowed      INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS blown_saves     INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS complete_games  INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS shutouts        INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS balks           INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS pickoffs        INT NOT NULL DEFAULT 0;

-- ── Step 2: Rewrite leaderboard functions ────────────────────────────────────

CREATE OR REPLACE FUNCTION fantasy_batter_leaderboard(
  p_season INT,
  p_limit  INT,
  p_offset INT
)
RETURNS TABLE(
  player_id  INT,
  full_name  TEXT,
  team       TEXT,
  "position" TEXT,
  total_pts  FLOAT,
  total_pa   BIGINT
)
LANGUAGE SQL STABLE AS $$
  SELECT
    s.player_id,
    pl.full_name,
    pl.team,
    pl.position,
    (
        s.total_bases * 1.0   -- TB  (+1)
      + s.runs        * 1.0   -- R   (+1)
      + s.rbi         * 1.0   -- RBI (+1)
      + s.bb          * 1.0   -- BB  (+1)
      + s.sb          * 1.0   -- SB  (+1)
      - s.so          * 1.0   -- SO  (-1)
      -- HBP removed from scoring; E not tracked in season stats
    )                          AS total_pts,
    s.pa::BIGINT               AS total_pa
  FROM player_season_stats s
  JOIN players pl ON pl.player_id = s.player_id
  WHERE s.season_year = p_season
    AND s.pa > 0
  ORDER BY total_pts DESC
  LIMIT  p_limit
  OFFSET p_offset
$$;


CREATE OR REPLACE FUNCTION fantasy_pitcher_leaderboard(
  p_season INT,
  p_limit  INT,
  p_offset INT
)
RETURNS TABLE(
  player_id  INT,
  full_name  TEXT,
  team       TEXT,
  "position" TEXT,
  total_pts  FLOAT,
  total_bf   BIGINT
)
LANGUAGE SQL STABLE AS $$
  SELECT
    s.player_id,
    pl.full_name,
    pl.team,
    pl.position,
    (
        s.outs_recorded  * 1.0   -- IP*3: each out = 1 pt
      + s.k              * 1.0   -- K    (+1)
      - s.h_allowed      * 1.0   -- H    (-1)
      - s.er             * 1.0   -- ER   (-1)
      - s.hr_allowed     * 1.0   -- HR   (-1)
      - s.bb_allowed     * 1.0   -- BB   (-1)
      + s.hbp_allowed    * 1.0   -- HB   (+1)
      + s.wins           * 5.0   -- W    (+5)
      - s.losses         * 5.0   -- L    (-5)
      + s.saves          * 5.0   -- SV   (+5)
      - s.blown_saves    * 5.0   -- BS   (-5)
      + s.complete_games * 3.0   -- CG   (+3)
      + s.shutouts       * 5.0   -- SHO  (+5)
      - s.balks          * 10.0  -- B    (-10)
      + s.pickoffs       * 2.0   -- PKO  (+2)
      -- NH(+10) and PG(+11) not tracked in season stats
    )                             AS total_pts,
    s.bf::BIGINT                  AS total_bf
  FROM player_season_stats s
  JOIN players pl ON pl.player_id = s.player_id
  WHERE s.season_year = p_season
    AND s.outs_recorded > 0
  ORDER BY total_pts DESC
  LIMIT  p_limit
  OFFSET p_offset
$$;
