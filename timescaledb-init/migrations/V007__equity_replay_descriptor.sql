-- Existing successful runs remain intact and retain NULL replay metadata.
ALTER TABLE backtest_runs
    ADD COLUMN IF NOT EXISTS replay_descriptor JSONB;
