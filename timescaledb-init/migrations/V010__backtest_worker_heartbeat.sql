-- Operational telemetry only. Old process rows may be pruned; they never own capacity.
CREATE TABLE backtest_worker_heartbeats (
    worker_id VARCHAR(36) PRIMARY KEY,
    owner_token VARCHAR(36),
    heartbeat_at TIMESTAMPTZ NOT NULL,
    fault_code VARCHAR(64),
    fault_message TEXT
);

CREATE INDEX idx_backtest_worker_heartbeats_recent
    ON backtest_worker_heartbeats (heartbeat_at DESC);
