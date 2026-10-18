-- V005 predates the complete legacy-shape audit. Keep V005 immutable for
-- databases that already ledgered it, then prevent an unsupported shape from
-- being recorded as current by validating the resulting table here.
DO $$
DECLARE
    schema_is_supported BOOLEAN;
BEGIN
    WITH expected_columns(column_name, data_type, is_not_null) AS (
        VALUES
            ('run_id', 'character varying(36)', TRUE),
            ('trade_sequence', 'integer', TRUE),
            ('trade_id', 'character varying(64)', TRUE),
            ('symbol', 'character varying(32)', TRUE),
            ('trade_direction', 'character varying(8)', TRUE),
            ('quantity', 'double precision', TRUE),
            ('entry_timestamp_ms', 'bigint', TRUE),
            ('entry_price', 'double precision', TRUE),
            ('exit_timestamp_ms', 'bigint', TRUE),
            ('exit_price', 'double precision', TRUE),
            ('stop_loss_price', 'double precision', FALSE),
            ('take_profit_price', 'double precision', FALSE),
            ('realized_pnl', 'double precision', TRUE),
            ('fees', 'double precision', TRUE),
            ('exit_reason', 'character varying(32)', TRUE)
    ),
    actual_columns AS (
        SELECT
            attributes.attname AS column_name,
            format_type(attributes.atttypid, attributes.atttypmod) AS data_type,
            attributes.attnotnull AS is_not_null
        FROM pg_attribute attributes
        WHERE attributes.attrelid = 'backtest_closed_trades'::regclass
          AND attributes.attnum > 0
          AND NOT attributes.attisdropped
    ),
    column_shape_matches AS (
        SELECT NOT EXISTS (
            SELECT 1
            FROM actual_columns
            FULL OUTER JOIN expected_columns USING (column_name)
            WHERE actual_columns.column_name IS NULL
               OR expected_columns.column_name IS NULL
               OR actual_columns.data_type <> expected_columns.data_type
               OR actual_columns.is_not_null <> expected_columns.is_not_null
        ) AS matches
    ),
    constraint_shape_matches AS (
        SELECT
            EXISTS (
                SELECT 1
                FROM pg_constraint constraints
                WHERE constraints.conrelid = 'backtest_closed_trades'::regclass
                  AND constraints.contype = 'p'
                  AND constraints.convalidated
                  AND constraints.conkey = ARRAY[
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.conrelid AND attname = 'run_id'
                      ),
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.conrelid
                            AND attname = 'trade_sequence'
                      )
                  ]::SMALLINT[]
            )
            AND EXISTS (
                SELECT 1
                FROM pg_constraint constraints
                WHERE constraints.conrelid = 'backtest_closed_trades'::regclass
                  AND constraints.contype = 'u'
                  AND constraints.convalidated
                  AND constraints.conkey = ARRAY[
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.conrelid AND attname = 'run_id'
                      ),
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.conrelid AND attname = 'trade_id'
                      )
                  ]::SMALLINT[]
            )
            AND EXISTS (
                SELECT 1
                FROM pg_constraint constraints
                WHERE constraints.conrelid = 'backtest_closed_trades'::regclass
                  AND constraints.contype = 'f'
                  AND constraints.confrelid = 'backtest_runs'::regclass
                  AND constraints.convalidated
                  AND NOT constraints.condeferrable
                  AND constraints.confdeltype = 'c'
                  AND constraints.confupdtype = 'a'
                  AND constraints.confmatchtype = 's'
                  AND constraints.conkey = ARRAY[
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.conrelid AND attname = 'run_id'
                      )
                  ]::SMALLINT[]
                  AND constraints.confkey = ARRAY[
                      (
                          SELECT attnum FROM pg_attribute
                          WHERE attrelid = constraints.confrelid AND attname = 'run_id'
                      )
                  ]::SMALLINT[]
            )
            AND EXISTS (
                SELECT 1
                FROM pg_constraint constraints
                WHERE constraints.conrelid = 'backtest_closed_trades'::regclass
                  AND constraints.contype = 'c'
                  AND constraints.convalidated
                  AND pg_get_constraintdef(constraints.oid) =
                      'CHECK (((exit_reason)::text = ANY ((ARRAY['
                      || '''signal''::character varying, '
                      || '''stop_loss''::character varying, '
                      || '''take_profit''::character varying])::text[])))'
            )
            AND EXISTS (
                SELECT 1
                FROM pg_constraint constraints
                WHERE constraints.conrelid = 'backtest_closed_trades'::regclass
                  AND constraints.contype = 'c'
                  AND constraints.convalidated
                  AND pg_get_constraintdef(constraints.oid) =
                      'CHECK (((trade_direction)::text = ANY ((ARRAY['
                      || '''long''::character varying, '
                      || '''short''::character varying])::text[])))'
            ) AS matches
    )
    SELECT column_shape_matches.matches AND constraint_shape_matches.matches
    INTO schema_is_supported
    FROM column_shape_matches, constraint_shape_matches;

    IF NOT schema_is_supported THEN
        RAISE EXCEPTION
            'Unsupported backtest_closed_trades schema; rebuild the durable '
            'backtest tables before rerunning migration V006';
    END IF;
END
$$;
