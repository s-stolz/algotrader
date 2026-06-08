-- Deliberate one-time reset of backtest persistence.
-- This migration is destructive only for backtest tables. It must be run
-- explicitly for an existing database and is not part of application startup.

SELECT 'CREATE DATABASE finance_data'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'finance_data'
)\gexec

\c finance_data;

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

DROP TABLE IF EXISTS backtest_fills;
DROP TABLE IF EXISTS backtest_closed_trades;
DROP TABLE IF EXISTS backtest_runs;
DROP TABLE IF EXISTS backtest_run_summaries;

CREATE TABLE backtest_runs (
    run_id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(16) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code VARCHAR(64),
    error_message TEXT,
    request_schema_version INTEGER NOT NULL,
    request JSONB NOT NULL,
    result_schema_version INTEGER,
    metrics JSONB,
    diagnostics JSONB,
    CONSTRAINT backtest_runs_status_check
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))
);

CREATE INDEX idx_backtest_runs_submitted_at
    ON backtest_runs (submitted_at DESC, run_id);

CREATE INDEX idx_backtest_runs_status_submitted_at
    ON backtest_runs (status, submitted_at, run_id);

CREATE TABLE backtest_fills (
    run_id VARCHAR(36) NOT NULL,
    fill_sequence INTEGER NOT NULL,
    timestamp_ms BIGINT NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION NOT NULL,
    exit_reason VARCHAR(32),
    FOREIGN KEY (run_id) REFERENCES backtest_runs (run_id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, fill_sequence),
    CONSTRAINT backtest_fills_side_check CHECK (side IN ('buy', 'sell')),
    CONSTRAINT backtest_fills_exit_reason_check
        CHECK (
            exit_reason IS NULL
            OR exit_reason IN ('signal', 'stop_loss', 'take_profit')
        )
);

CREATE INDEX idx_backtest_fills_run_order
    ON backtest_fills (run_id, timestamp_ms, fill_sequence);

CREATE TABLE backtest_closed_trades (
    run_id VARCHAR(36) NOT NULL,
    trade_sequence INTEGER NOT NULL,
    trade_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_timestamp_ms BIGINT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_timestamp_ms BIGINT NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    realized_pnl DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION NOT NULL,
    exit_reason VARCHAR(32) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES backtest_runs (run_id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, trade_sequence),
    CONSTRAINT uq_backtest_closed_trades_identity UNIQUE (run_id, trade_id),
    CONSTRAINT backtest_closed_trades_exit_reason_check
        CHECK (exit_reason IN ('signal', 'stop_loss', 'take_profit'))
);

CREATE INDEX idx_backtest_closed_trades_run_order
    ON backtest_closed_trades (
        run_id,
        entry_timestamp_ms,
        exit_timestamp_ms,
        trade_sequence
    );
