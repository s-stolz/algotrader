-- Pre-ledger databases may already have this table at an older result-schema
-- version. Protective prices are nullable and can be added without changing the
-- meaning of existing rows. Direction cannot be reconstructed safely from a
-- closed trade, so only an empty directionless table can be upgraded in place.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('run_id'),
                ('trade_sequence'),
                ('trade_id'),
                ('symbol'),
                ('quantity'),
                ('entry_timestamp_ms'),
                ('entry_price'),
                ('exit_timestamp_ms'),
                ('exit_price'),
                ('realized_pnl'),
                ('fees'),
                ('exit_reason')
        ) AS required_columns(column_name)
        WHERE NOT EXISTS (
            SELECT 1
            FROM information_schema.columns existing_columns
            WHERE existing_columns.table_schema = current_schema()
              AND existing_columns.table_name = 'backtest_closed_trades'
              AND existing_columns.column_name = required_columns.column_name
        )
    ) THEN
        RAISE EXCEPTION
            'Unsupported legacy backtest_closed_trades table shape; rebuild the '
            'durable backtest tables before rerunning the migration';
    END IF;
END
$$;

ALTER TABLE backtest_closed_trades
    ADD COLUMN IF NOT EXISTS stop_loss_price DOUBLE PRECISION;

ALTER TABLE backtest_closed_trades
    ADD COLUMN IF NOT EXISTS take_profit_price DOUBLE PRECISION;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'backtest_closed_trades'
          AND column_name = 'trade_direction'
    ) THEN
        IF EXISTS (SELECT 1 FROM backtest_closed_trades) THEN
            RAISE EXCEPTION
                'Cannot safely infer trade_direction for existing '
                'backtest_closed_trades rows; export or delete legacy results, '
                'empty the table, and rerun the migration';
        END IF;

        ALTER TABLE backtest_closed_trades
            ADD COLUMN trade_direction VARCHAR(8);
    END IF;

    IF EXISTS (
        SELECT 1
        FROM backtest_closed_trades
        WHERE trade_direction IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot make backtest_closed_trades.trade_direction required while '
            'legacy rows contain NULL; repair or delete those rows and rerun '
            'the migration';
    END IF;

    ALTER TABLE backtest_closed_trades
        ALTER COLUMN trade_direction SET NOT NULL;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'backtest_closed_trades_trade_direction_check'
          AND conrelid = 'backtest_closed_trades'::regclass
    ) THEN
        ALTER TABLE backtest_closed_trades
            ADD CONSTRAINT backtest_closed_trades_trade_direction_check
            CHECK (trade_direction IN ('long', 'short'));
    END IF;
END
$$;
