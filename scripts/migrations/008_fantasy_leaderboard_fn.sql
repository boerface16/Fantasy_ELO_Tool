-- Fantasy season leaderboard PostgreSQL functions
-- Called via supabase.rpc() from the FastAPI backend
-- Run in Supabase SQL Editor or: psql $DATABASE_URL -f scripts/migrations/008_fantasy_leaderboard_fn.sql

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
    pa.batter_id                        AS player_id,
    pl.full_name,
    pl.team,
    pl.position,
    (
      -- TB * 1.85  (TB=1 + R_est=0.40 + RBI_est=0.45)
      (  COUNT(*) FILTER (WHERE pa.result_type = 'Single')
       + COUNT(*) FILTER (WHERE pa.result_type = 'Double')  * 2
       + COUNT(*) FILTER (WHERE pa.result_type = 'Triple')  * 3
       + COUNT(*) FILTER (WHERE pa.result_type = 'HR')      * 4
      ) * 1.85
      + COUNT(*) FILTER (WHERE pa.result_type IN ('BB','IBB','HBP')) * 1.0
      + COUNT(*) FILTER (WHERE pa.result_type = 'SB')                * 1.0
      - COUNT(*) FILTER (WHERE pa.result_type = 'StrikeOut')         * 1.0
    )                                   AS total_pts,
    COUNT(*)                            AS total_pa
  FROM plate_appearances pa
  JOIN players pl ON pl.player_id = pa.batter_id
  WHERE pa.season_year = p_season
  GROUP BY pa.batter_id, pl.full_name, pl.team, pl.position
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
    pa.pitcher_id                       AS player_id,
    pl.full_name,
    pl.team,
    pl.position,
    (
      -- IP*3 component: outs (including K) * 1
      COUNT(*) FILTER (WHERE pa.result_type IN ('OUT','POPUP','GROUNDOUT','StrikeOut')) * 1.0
      -- K bonus (+1 on top of the out)
      + COUNT(*) FILTER (WHERE pa.result_type = 'StrikeOut') * 1.0
      -- H allowed (-1 each)
      - COUNT(*) FILTER (WHERE pa.result_type IN ('Single','Double','Triple','HR')) * 1.0
      -- ER estimate: (H + BB) * 0.30 * -2  →  * -0.60
      - ( COUNT(*) FILTER (WHERE pa.result_type IN ('Single','Double','Triple','HR'))
        + COUNT(*) FILTER (WHERE pa.result_type IN ('BB','IBB','HBP'))
        ) * 0.6
      -- BB penalty (-1 each)
      - COUNT(*) FILTER (WHERE pa.result_type IN ('BB','IBB','HBP')) * 1.0
    )                                   AS total_pts,
    COUNT(*)                            AS total_bf
  FROM plate_appearances pa
  JOIN players pl ON pl.player_id = pa.pitcher_id
  WHERE pa.season_year = p_season
  GROUP BY pa.pitcher_id, pl.full_name, pl.team, pl.position
  ORDER BY total_pts DESC
  LIMIT  p_limit
  OFFSET p_offset
$$;
