# TimescaleDB Init Context

SQL bootstrap and migration files for the `finance_data` TimescaleDB database.

## Owned Interfaces

- Timescale schema for Markets and Candles.
- Raw Candle storage in `candles` with `timestamp_utc`.
- Continuous aggregate views and refresh policies for higher Timeframes.
- Idempotent SQL bootstrap and retune behavior for local databases.
- Durable backtest lifecycle, request/result JSONB, fill, and trade tables.

## Key Files

- `01-init.sql`: database, extension, market/candle tables, and durable backtest
  lifecycle/result tables.
- `02-migrate-timestamps.sql`: timestamp migration support.
- `03-optimize-candles.sql`: hypertable setup, compression, indexes, continuous
  aggregates, and aggregate policies.
- `04-retune-cagg-and-index.sql`: continuous aggregate policy retuning and
  historical refresh.
- `05-backtest-result-schema-v2.sql`: existing-volume migration for nullable
  backtest closed-trade protective exit prices.

## Contracts

- Raw candles are stored in `candles` with `timestamp_utc TIMESTAMPTZ`.
- Primary key is `(symbol_id, timestamp_utc)`.
- Current continuous aggregate views include M5, M15, M30, H1, H4, and D1.
- Database-accessor-api may fall back to direct bucketing if an aggregate view is
  unavailable or not useful for the requested range.
- `backtest_runs` stores normalized lifecycle fields, request/result schema
  versions, immutable request JSONB, and nullable metrics/diagnostics JSONB.
- `backtest_fills` and `backtest_closed_trades` use per-run sequence keys for
  deterministic ordering and cascade when the parent run is deleted.
- `backtest_closed_trades` includes explicit trade direction plus nullable
  planned protective exit prices for stop-loss and take-profit overlays. Result
  schema version 3 requires trade direction. The adoption path may delete old
  local backtest runs rather than reading legacy result artifacts.
- `backtest_closed_trades.trade_direction` is required and constrained to
  `long` or `short`.
- Request schema version 2 and result schema version 3 adoption require schema
  migration only; existing local durable backtest rows may be deleted instead of
  rewritten.
- The trade-direction schema migration may assume `backtest_closed_trades` is
  empty when adding the required constrained column.
- Fresh database initialization creates the complete durable backtest schema
  without a separate destructive reset script.
- Existing database volumes created before result schema version 2 need the
  idempotent `05-backtest-result-schema-v2.sql` migration applied manually.

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
