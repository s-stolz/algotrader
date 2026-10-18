ALTER TABLE IF EXISTS markets
ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'candles'
          AND column_name = 'timestamp'
    ) THEN
        ALTER TABLE candles ADD COLUMN IF NOT EXISTS timestamp_utc TIMESTAMPTZ;

        UPDATE candles
        SET timestamp_utc = "timestamp" AT TIME ZONE 'UTC'
        WHERE timestamp_utc IS NULL;

        ALTER TABLE candles DROP CONSTRAINT IF EXISTS candles_pkey;
        ALTER TABLE candles ALTER COLUMN timestamp_utc SET NOT NULL;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'candles_pkey'
              AND conrelid = 'candles'::regclass
        ) THEN
            ALTER TABLE candles ADD CONSTRAINT candles_pkey PRIMARY KEY (symbol_id, timestamp_utc);
        END IF;

        ALTER TABLE candles DROP COLUMN IF EXISTS "timestamp";
    END IF;
END $$;
