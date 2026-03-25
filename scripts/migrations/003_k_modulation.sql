-- Phase 7: K-Modulation (Hybrid A1+C2)
-- elo_pa_detail에 K-modulation 추적 컬럼 추가

ALTER TABLE elo_pa_detail ADD COLUMN IF NOT EXISTS k_base REAL;
ALTER TABLE elo_pa_detail ADD COLUMN IF NOT EXISTS physics_mod REAL;
ALTER TABLE elo_pa_detail ADD COLUMN IF NOT EXISTS k_effective REAL;
