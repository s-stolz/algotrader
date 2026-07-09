# TimescaleDB Init Context

Image-owned SQL bootstrap and ledgered migration files for the configured
TimescaleDB database.

## Owned Interfaces

- Timescale schema for Markets and Candles.
- Raw Candle storage in `candles` with `timestamp_utc`.
- Continuous aggregate views and refresh policies for higher Timeframes.
- Idempotent SQL bootstrap and retune behavior for local databases.
- Forward-only TimescaleDB migrations recorded in `schema_migrations`.
- Durable backtest lifecycle, request/result JSONB, fill, and trade tables.

## Key Files

- `Dockerfile`: TimescaleDB image with validated bootstrap tooling and migration
  files installed under `/docker-entrypoint-initdb.d`.
- `01-run-migrations.sh`: bootstrap-only migration application for fresh Docker
  volumes.
- `migrations/V001__base_schema.sql`: extension, market/candle tables, and
  durable backtest lifecycle/result tables.
- `migrations/V002__timestamp_utc.sql`: timestamp migration support.
- `migrations/V003__optimize_candles.sql`: hypertable setup, compression,
  indexes, continuous aggregates, and aggregate policies.
- `migrations/V004__retune_cagg_and_index.sql`: continuous aggregate policy
  retuning and historical refresh.
- `migrations/V005__upgrade_legacy_closed_trades.sql`: explicit upgrade or
  rejection for supported pre-ledger closed-trade table shapes.
- `migrations/V006__audit_closed_trades_schema.sql`: complete structural audit
  of the closed-trade table after the legacy upgrade.

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
  schema version 3 is the only accepted completed-result schema.
- `backtest_closed_trades.trade_direction` is required and constrained to
  `long` or `short`.
- Request schema version 2 is current for request JSON; result schema version 3
  is current for completed result artifacts.
- Fresh database initialization creates the complete durable backtest schema
  without a separate destructive reset script.
- The TimescaleDB image entrypoint creates the database named by generated
  `POSTGRES_DB` before it runs `01-run-migrations.sh`; bootstrap SQL does not
  hard-code or separately create a database.
- The TimescaleDB container receives non-secret shared configuration separately
  from its database password secret file.
- Runtime migrations use strict `VNNN__description.sql` filenames and are applied
  once, in order, with checksums recorded in `schema_migrations`.
- Existing databases that match the historical schema may baseline `V001`-`V002`
  into `schema_migrations`. `V003` and `V004` are always replayed because their
  policy/compression and historical-refresh effects cannot all be inferred
  reliably from catalog state.
- Compatible legacy closed-trade tables are upgraded by `V005`; populated
  directionless tables fail there. `V006` audits the complete resulting column,
  key, relationship, and enum-check shape so structurally unsupported databases
  fail with recovery guidance instead of being marked current.
- Concurrent runners are excluded by a session-scoped PostgreSQL advisory lock,
  which PostgreSQL releases automatically if the runner disconnects or dies.
- Migration rollback is modeled as a later forward migration, not a down script.

## Change Triggers

- If adding Timeframe support, update this directory, `database-accessor-api`,
  `libs/db_accessor_client`, frontend Timeframe options, and relevant service
  contexts.
- Keep migration SQL transactional where possible. Changes after a migration is
  applied must be added as a later `VNNN` file instead of editing the applied
  migration.
- If bootstrap or migration runner behavior changes, update ADR-0006.
- If Market or Candle storage shape changes, update root `CONTEXT.md` and
  `docs/agent/CONTRACT-CHANGES.md` if the cross-service interface changes.

## Verification

- Validate affected SQL against a local database when changing schema or
  aggregate behavior.
- Run database accessor and affected consumer tests when query semantics change.
