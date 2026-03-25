-- Phase 6: Two-Way Player ELO 분리
-- player_elo에 batting/pitching 분리 컬럼 추가, daily_ohlc에 role 추가

-- 1. player_elo: 분리 ELO 컬럼 추가
ALTER TABLE player_elo ADD COLUMN IF NOT EXISTS batting_elo REAL DEFAULT 1500.0;
ALTER TABLE player_elo ADD COLUMN IF NOT EXISTS pitching_elo REAL DEFAULT 1500.0;
ALTER TABLE player_elo ADD COLUMN IF NOT EXISTS batting_pa INTEGER DEFAULT 0;
ALTER TABLE player_elo ADD COLUMN IF NOT EXISTS pitching_pa INTEGER DEFAULT 0;

-- 기존 데이터 마이그레이션: composite_elo → batting_elo / pitching_elo
-- (순수 타자는 batting_elo = composite_elo, 순수 투수는 pitching_elo = composite_elo)
-- 이 마이그레이션은 run_elo.py 전체 재계산 후 정확한 값으로 덮어씌워짐

-- 2. daily_ohlc: role 컬럼 추가
ALTER TABLE daily_ohlc ADD COLUMN IF NOT EXISTS role VARCHAR(10) DEFAULT 'BATTING';

-- 3. UNIQUE 제약 변경: (player_id, game_date, elo_type, role)
-- 기존 제약 삭제 후 재생성
ALTER TABLE daily_ohlc DROP CONSTRAINT IF EXISTS daily_ohlc_player_id_game_date_elo_type_key;
ALTER TABLE daily_ohlc ADD CONSTRAINT daily_ohlc_player_date_type_role_key
  UNIQUE (player_id, game_date, elo_type, role);
