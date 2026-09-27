ALTER TABLE backtest_runs DROP CONSTRAINT backtest_runs_status_check;
ALTER TABLE backtest_runs ADD CONSTRAINT backtest_runs_status_check
    CHECK (status IN ('queued', 'running', 'cancelling', 'succeeded', 'failed', 'cancelled'));

ALTER TABLE backtest_runs
    ADD COLUMN cancel_requested_at TIMESTAMPTZ,
    ADD COLUMN cancellation_source VARCHAR(32),
    ADD COLUMN cancellation_reason TEXT;

ALTER TABLE backtest_runs ADD CONSTRAINT backtest_run_cancellation_check CHECK (
    (cancel_requested_at IS NULL AND cancellation_source IS NULL AND cancellation_reason IS NULL)
    OR (cancel_requested_at IS NOT NULL AND cancellation_source IS NOT NULL
        AND cancellation_reason IS NOT NULL)
);

ALTER TABLE backtest_runs ADD CONSTRAINT backtest_run_cancel_status_check CHECK (
    (status NOT IN ('cancelling', 'cancelled') OR cancel_requested_at IS NOT NULL)
    AND (status <> 'cancelling' OR completed_at IS NULL)
    AND (status <> 'cancelled' OR completed_at IS NOT NULL)
);
