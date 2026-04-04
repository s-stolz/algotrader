-- Retune existing databases after introducing broader cagg windows
-- and add an index optimized for latest-M1 reads.
--
-- Safe to run multiple times.

CREATE INDEX IF NOT EXISTS idx_candles_symbol_ts_desc_cover
ON candles (symbol_id, timestamp_utc DESC)
INCLUDE (open, high, low, close, volume);

DO $$
BEGIN
    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_m5');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;

    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_m15');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;

    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_m30');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;

    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_h1');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;

    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_h4');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;

    BEGIN
        PERFORM remove_continuous_aggregate_policy('candles_agg_d1');
    EXCEPTION
        WHEN OTHERS THEN NULL;
    END;
END $$;

SELECT add_continuous_aggregate_policy(
    'candles_agg_m5',
    start_offset => INTERVAL '180 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_m15',
    start_offset => INTERVAL '365 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_m30',
    start_offset => INTERVAL '365 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_h1',
    start_offset => INTERVAL '730 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_h4',
    start_offset => INTERVAL '1825 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_d1',
    start_offset => INTERVAL '3650 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- One-time backfill of historical range into continuous aggregates.
-- If history is very large this can take time.
DO $$
DECLARE
    min_ts TIMESTAMPTZ;
    max_ts TIMESTAMPTZ;
BEGIN
    SELECT MIN(timestamp_utc), MAX(timestamp_utc)
    INTO min_ts, max_ts
    FROM candles;

    IF min_ts IS NULL OR max_ts IS NULL THEN
        RETURN;
    END IF;

    CALL refresh_continuous_aggregate('candles_agg_m5', min_ts, max_ts + INTERVAL '1 day');
    CALL refresh_continuous_aggregate('candles_agg_m15', min_ts, max_ts + INTERVAL '1 day');
    CALL refresh_continuous_aggregate('candles_agg_m30', min_ts, max_ts + INTERVAL '1 day');
    CALL refresh_continuous_aggregate('candles_agg_h1', min_ts, max_ts + INTERVAL '1 day');
    CALL refresh_continuous_aggregate('candles_agg_h4', min_ts, max_ts + INTERVAL '1 day');
    CALL refresh_continuous_aggregate('candles_agg_d1', min_ts, max_ts + INTERVAL '1 day');
END $$;
