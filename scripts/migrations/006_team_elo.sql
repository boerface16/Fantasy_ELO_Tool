-- 006_team_elo.sql
-- FiveThirtyEight-style team ELO ratings

CREATE TABLE IF NOT EXISTS team_elo (
    id BIGSERIAL PRIMARY KEY,
    team_code TEXT NOT NULL,
    game_date DATE NOT NULL,
    game_pk INT NOT NULL,
    elo_before FLOAT NOT NULL,
    elo_after FLOAT NOT NULL,
    opponent_code TEXT NOT NULL,
    result TEXT NOT NULL,          -- 'W' or 'L'
    run_diff INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_code, game_date, opponent_code, game_pk)
);

CREATE INDEX IF NOT EXISTS idx_team_elo_team_date ON team_elo(team_code, game_date DESC);
CREATE INDEX IF NOT EXISTS idx_team_elo_date ON team_elo(game_date DESC);
