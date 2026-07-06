-- Migration for backtest result schema version 3. Adds required closed-trade
-- direction for clean durable backtest tables; legacy row backfill is out of
-- scope for this rollout.
\c finance_data;

ALTER TABLE IF EXISTS backtest_closed_trades
    ADD COLUMN IF NOT EXISTS trade_direction VARCHAR(8);

ALTER TABLE IF EXISTS backtest_closed_trades
    ALTER COLUMN trade_direction SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'backtest_closed_trades'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'backtest_closed_trades_trade_direction_check'
          AND conrelid = to_regclass('backtest_closed_trades')
    ) THEN
        ALTER TABLE backtest_closed_trades
            ADD CONSTRAINT backtest_closed_trades_trade_direction_check
            CHECK (trade_direction IN ('long', 'short'));
    END IF;
END
$$;
