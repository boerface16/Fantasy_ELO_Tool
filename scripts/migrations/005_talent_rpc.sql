-- Phase 9: Talent ELO RPC function for player talent radar
CREATE OR REPLACE FUNCTION get_player_talent_radar(p_player_id INTEGER)
RETURNS TABLE (
  talent_type VARCHAR,
  player_role VARCHAR,
  season_elo REAL,
  career_elo REAL,
  season_rank BIGINT,
  career_rank BIGINT,
  total_in_role BIGINT
) AS $$
  SELECT
    sub.talent_type,
    sub.player_role,
    sub.season_elo,
    sub.career_elo,
    sub.season_rank,
    sub.career_rank,
    sub.total_in_role
  FROM (
    SELECT
      t.player_id,
      t.talent_type,
      t.player_role,
      t.season_elo,
      t.career_elo,
      RANK() OVER (PARTITION BY t.talent_type, t.player_role ORDER BY t.season_elo DESC) AS season_rank,
      RANK() OVER (PARTITION BY t.talent_type, t.player_role ORDER BY t.career_elo DESC) AS career_rank,
      COUNT(*) OVER (PARTITION BY t.talent_type, t.player_role) AS total_in_role
    FROM talent_player_current t
  ) sub
  WHERE sub.player_id = p_player_id;
$$ LANGUAGE sql STABLE;
