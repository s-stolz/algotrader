-- Backtester persistence foundation schema.
-- Idempotent and safe to run after the base database bootstrap.

SELECT 'CREATE DATABASE finance_data'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'finance_data'
)\gexec

\c finance_data;

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE TABLE IF NOT EXISTS backtest_run_summaries (
    run_id VARCHAR(36) PRIMARY KEY,
    persisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execution_duration_ms INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    engine VARCHAR(32) NOT NULL,
    strategy_id VARCHAR(128) NOT NULL,
    start_ms BIGINT NOT NULL,
    end_ms BIGINT NOT NULL,
    initial_capital DOUBLE PRECISION NOT NULL,
    final_equity DOUBLE PRECISION NOT NULL,
    final_cash DOUBLE PRECISION NOT NULL,
    final_position_symbol VARCHAR(32),
    final_position_quantity DOUBLE PRECISION NOT NULL,
    total_return_pct DOUBLE PRECISION NOT NULL,
    max_drawdown_pct DOUBLE PRECISION NOT NULL,
    trade_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_run_summaries_persisted_at
    ON backtest_run_summaries (persisted_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_run_summaries_filters
    ON backtest_run_summaries (symbol, timeframe, strategy_id, engine);

CREATE TABLE IF NOT EXISTS backtest_closed_trades (
    run_id VARCHAR(36) NOT NULL,
    trade_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_timestamp_ms BIGINT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_timestamp_ms BIGINT NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    realized_pnl DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (run_id) REFERENCES backtest_run_summaries (run_id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, trade_id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_closed_trades_run_id
    ON backtest_closed_trades (run_id);
