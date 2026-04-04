-- Migration 007: Add bb_type and runner_id columns to plate_appearances
-- bb_type: batted ball type (popup, ground_ball, fly_ball, line_drive) — null for non-BIP events
-- runner_id: player ID of the baserunner for SB/CS events (null for normal PAs)

ALTER TABLE plate_appearances
  ADD COLUMN IF NOT EXISTS bb_type   VARCHAR(20),
  ADD COLUMN IF NOT EXISTS runner_id INTEGER;
