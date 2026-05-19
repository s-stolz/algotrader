# TimescaleDB Init Context

SQL bootstrap and migration files for the `finance_data` TimescaleDB database.

## Owned Interfaces

- Timescale schema for Markets and Candles.
- Raw Candle storage in `candles` with `timestamp_utc`.
- Continuous aggregate views and refresh policies for higher Timeframes.
- Idempotent SQL bootstrap and retune behavior for local databases.

## Key Files

- `01-init.sql`: database, extension, `markets`, and `candles` tables.
- `02-migrate-timestamps.sql`: timestamp migration support.
- `03-optimize-candles.sql`: hypertable setup, compression, indexes, continuous
  aggregates, and aggregate policies.
- `04-retune-cagg-and-index.sql`: continuous aggregate policy retuning and
  historical refresh.

## Contracts

- Raw candles are stored in `candles` with `timestamp_utc TIMESTAMPTZ`.
- Primary key is `(symbol_id, timestamp_utc)`.
- Current continuous aggregate views include M5, M15, M30, H1, H4, and D1.
- Database-accessor-api may fall back to direct bucketing if an aggregate view is
  unavailable or not useful for the requested range.
- Backtest closed trades include `exit_reason` with `signal`, `stop_loss`, or
  `take_profit`; existing rows and missing payload values default to `signal`.

## Change Triggers

- If adding Timeframe support, update this directory, `database-accessor-api`,
  `libs/db_accessor_client`, frontend Timeframe options, and relevant service
  contexts.
- Keep SQL idempotent where possible because init and retune scripts may be run
  against existing local databases.
- If Market or Candle storage shape changes, update root `CONTEXT.md` and
  `docs/agent/CONTRACT-CHANGES.md` if the cross-service interface changes.

## Verification

- Validate affected SQL against a local database when changing schema or
  aggregate behavior.
- Run database accessor and affected consumer tests when query semantics change.
