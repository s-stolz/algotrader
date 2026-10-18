-- Command identity is durable across retries and worker restarts.
ALTER TABLE backtest_batch_events ADD COLUMN command_id VARCHAR(36);
CREATE UNIQUE INDEX uq_backtest_batch_command
    ON backtest_batch_events (batch_id, command_id)
    WHERE command_id IS NOT NULL;

-- No-op commands also need a receipt: the same ID must not be reinterpreted
-- after a later command changes the batch state.
CREATE TABLE backtest_batch_commands (
    batch_id VARCHAR(36) NOT NULL REFERENCES backtest_batches(batch_id) ON DELETE CASCADE,
    command_id VARCHAR(36) NOT NULL,
    command VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    lifecycle_revision INTEGER NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (batch_id, command_id),
    CONSTRAINT backtest_batch_command_type_check CHECK (command IN ('pause', 'resume'))
);
