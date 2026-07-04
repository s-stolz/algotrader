-- Create the database
CREATE DATABASE finance_data;

-- Connect to the newly created database
\c finance_data;

-- Create the extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Adjust user privileges as necessary

-- Create markets table
CREATE TABLE IF NOT EXISTS markets (
    symbol_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    market_type VARCHAR(20) NOT NULL,
    min_move FLOAT NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'
);

-- Create candles table
CREATE TABLE IF NOT EXISTS candles (
    symbol_id INTEGER NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume FLOAT NOT NULL,
    FOREIGN KEY (symbol_id) REFERENCES markets (symbol_id),
    PRIMARY KEY (symbol_id, timestamp_utc)
);

-- Create durable backtest lifecycle and result tables.
CREATE TABLE IF NOT EXISTS backtest_runs (
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

CREATE INDEX IF NOT EXISTS idx_backtest_runs_submitted_at
    ON backtest_runs (submitted_at DESC, run_id);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_status_submitted_at
    ON backtest_runs (status, submitted_at, run_id);

CREATE TABLE IF NOT EXISTS backtest_fills (
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

CREATE INDEX IF NOT EXISTS idx_backtest_fills_run_order
    ON backtest_fills (run_id, timestamp_ms, fill_sequence);

CREATE TABLE IF NOT EXISTS backtest_closed_trades (
    run_id VARCHAR(36) NOT NULL,
    trade_sequence INTEGER NOT NULL,
    trade_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_timestamp_ms BIGINT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_timestamp_ms BIGINT NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    stop_loss_price DOUBLE PRECISION,
    take_profit_price DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION NOT NULL,
    exit_reason VARCHAR(32) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES backtest_runs (run_id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, trade_sequence),
    CONSTRAINT uq_backtest_closed_trades_identity UNIQUE (run_id, trade_id),
    CONSTRAINT backtest_closed_trades_exit_reason_check
        CHECK (exit_reason IN ('signal', 'stop_loss', 'take_profit'))
);

CREATE INDEX IF NOT EXISTS idx_backtest_closed_trades_run_order
    ON backtest_closed_trades (
        run_id,
        entry_timestamp_ms,
        exit_timestamp_ms,
        trade_sequence
    );

ALTER TABLE IF EXISTS backtest_closed_trades
    ADD COLUMN IF NOT EXISTS stop_loss_price DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS take_profit_price DOUBLE PRECISION;
