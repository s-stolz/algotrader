ALTER TABLE backtest_batches
    ADD COLUMN cancel_requested_at TIMESTAMPTZ,
    ADD COLUMN cancellation_source VARCHAR(32),
    ADD COLUMN cancellation_reason TEXT;

ALTER TABLE backtest_batches ADD CONSTRAINT backtest_batch_cancellation_check CHECK (
    (cancel_requested_at IS NULL AND cancellation_source IS NULL AND cancellation_reason IS NULL)
    OR (cancel_requested_at IS NOT NULL AND cancellation_source IS NOT NULL
        AND cancellation_reason IS NOT NULL)
);

ALTER TABLE backtest_batch_commands DROP CONSTRAINT backtest_batch_command_type_check;
ALTER TABLE backtest_batch_commands ADD CONSTRAINT backtest_batch_command_type_check
    CHECK (command IN ('pause', 'resume', 'cancel'));
