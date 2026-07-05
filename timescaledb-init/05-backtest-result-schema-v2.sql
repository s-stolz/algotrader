-- Idempotent migration for existing databases created before backtest result
-- schema version 2. Adds nullable planned protective exit levels to closed
-- trade artifacts without modifying existing rows.
\c finance_data;

ALTER TABLE IF EXISTS backtest_closed_trades
    ADD COLUMN IF NOT EXISTS stop_loss_price DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS take_profit_price DOUBLE PRECISION;
