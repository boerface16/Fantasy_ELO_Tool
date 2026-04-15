-- Fantasy season leaderboard PostgreSQL functions
-- Called via supabase.rpc() from the FastAPI backend
-- Run in Supabase SQL Editor or: psql $DATABASE_URL -f scripts/migrations/008_fantasy_leaderboard_fn.sql
--
-- v3: Rewritten to use player_season_stats (sourced from MLB Stats API) for exact
--     ESPN H2H Points scoring. Previous versions estimated R/RBI from TB and were
--     missing W/SV/HLD/L for pitchers entirely.
--
-- Batter formula (exact ESPN):
--   TB(+1) + R(+1) + RBI(+1) + BB(+1) + HBP(+1) + SB(+1) + SO(-1)
--
-- Pitcher formula (exact ESPN):
--   IP*3(+3/IP) + K(+1) + H(-1) + ER(-2) + BB(-1) + HBP(-1)
--   + W(+2) + L(-2) + SV(+5) + HLD(+2)

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
        s.total_bases * 1.0   -- TB
      + s.runs        * 1.0   -- R
      + s.rbi         * 1.0   -- RBI
      + s.bb          * 1.0   -- BB
      + s.hbp         * 1.0   -- HBP
      + s.sb          * 1.0   -- SB
      - s.so          * 1.0   -- SO (penalty)
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
        s.outs_recorded * 1.0   -- IP*3: each out = 1 pt (since IP*3 pts = outs pts)
      + s.k             * 1.0   -- K  (+1)
      - s.h_allowed     * 1.0   -- H  (-1)
      - s.er            * 2.0   -- ER (-2)
      - s.bb_allowed    * 1.0   -- BB (-1)
      - s.hbp_allowed   * 1.0   -- HBP (-1)
      + s.wins          * 2.0   -- W  (+2)
      - s.losses        * 2.0   -- L  (-2)
      + s.saves         * 5.0   -- SV (+5)
      + s.holds         * 2.0   -- HLD (+2)
    )                            AS total_pts,
    -- Use outs_recorded as a proxy for batters faced (no exact BF in stats table)
    s.outs_recorded::BIGINT      AS total_bf
  FROM player_season_stats s
  JOIN players pl ON pl.player_id = s.player_id
  WHERE s.season_year = p_season
    AND s.outs_recorded > 0
  ORDER BY total_pts DESC
  LIMIT  p_limit
  OFFSET p_offset
$$;
