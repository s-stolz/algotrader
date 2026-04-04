-- Performance-focused TimescaleDB migration for candle reads.
-- Idempotent and safe to rerun.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'candles'
          AND c.relkind = 'r'
          AND n.nspname = 'public'
    ) THEN
        PERFORM create_hypertable(
            'candles',
            by_range('timestamp_utc', INTERVAL '1 day'),
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    END IF;
END $$;

ALTER TABLE IF EXISTS candles
SET (
    timescaledb.compress = true,
    timescaledb.compress_segmentby = 'symbol_id',
    timescaledb.compress_orderby = 'timestamp_utc DESC'
);

SELECT add_compression_policy('candles', INTERVAL '7 days', if_not_exists => TRUE);

-- Optimize latest-M1 history reads:
-- query shape is symbol filter + timestamp DESC + limit, while selecting OHLCV.
CREATE INDEX IF NOT EXISTS idx_candles_symbol_ts_desc_cover
ON candles (symbol_id, timestamp_utc DESC)
INCLUDE (open, high, low, close, volume);

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_m5
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '5 minutes', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_m15
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '15 minutes', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_m30
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '30 minutes', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_h1
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_h4
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '4 hours', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_agg_d1
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 day', timestamp_utc) AS bucket_ts,
    symbol_id,
    first(open, timestamp_utc) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    last(close, timestamp_utc) AS close,
    SUM(volume) AS volume
FROM candles
GROUP BY bucket_ts, symbol_id
WITH NO DATA;

ALTER MATERIALIZED VIEW candles_agg_m5 SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW candles_agg_m15 SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW candles_agg_m30 SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW candles_agg_h1 SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW candles_agg_h4 SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW candles_agg_d1 SET (timescaledb.materialized_only = false);

SELECT add_continuous_aggregate_policy(
    'candles_agg_m5',
    start_offset => INTERVAL '90 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_m15',
    start_offset => INTERVAL '90 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_m30',
    start_offset => INTERVAL '180 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_h1',
    start_offset => INTERVAL '180 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_h4',
    start_offset => INTERVAL '365 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'candles_agg_d1',
    start_offset => INTERVAL '365 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);
