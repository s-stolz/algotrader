# TimescaleDB Context

Owns SQL bootstrap, hypertables, continuous aggregates, and forward-only schema
migrations. Runtime query behavior belongs to
[database-accessor-api](../database-accessor-api/CONTEXT.md).

## Migration Discipline

- `migrations/` is the migration inventory. Add the next `VNNN__description.sql`;
  applied migrations are immutable and reversions use later forward migrations.
- `scripts/migrate_db.py` validates order/checksums against `schema_migrations`.
  A session-scoped PostgreSQL advisory lock excludes concurrent runners and is
  released on disconnect. Keep each migration transactional where supported.
- The image installs migrations and bootstrap tooling; `01-run-migrations.sh`
  applies them on fresh volumes. The upstream entrypoint creates the generated
  `POSTGRES_DB` first. Existing volumes use `make migrate-db`.
- Fresh databases run the complete migration chain. Existing databases require
  a valid ledger; automatic adoption of pre-ledger installations is unsupported.
  Keep V005/V006 and their checks: ledgered upgrades still use the immutable chain.
- For rationale or runner changes, read [ADR-0006](../docs/adr/0006-ledgered-timescaledb-migrations.md).
  For upgrades with queued/running backtests, follow
  [worker cutover](../docs/operations/backtest-worker-recovery.md#upgrade-with-queued-or-running-work).

## Storage Invariants

- Raw M1 candles use `timestamp_utc TIMESTAMPTZ`, keyed by
  `(symbol_id, timestamp_utc)`. Higher-Timeframe reads can use continuous
  aggregates or accessor bucketing fallback. Inspect migration SQL for current
  view definitions and refresh policies.
- [Backtest contracts](../docs/contracts/backtests.md) owns lifecycle, snapshot,
  membership, and deletion rules. SQL constraints/triggers protect immutable
  requests and fixed membership; whole-Backtest deletion cascades while direct member
  deletion remains guarded.
- Lifecycle fields are normalized; versioned request/result documents and nullable
  replay metadata use JSONB. Schema-version changes do not necessarily require
  SQL changes. Preserve historical rows without manufacturing missing metadata.
- V020 discards existing backtest history during the unified-model cutover and
  makes every Run's Backtest ID and ordinal mandatory. It refuses a held/faulted
  slot; Markets and Candles are retained. Follow the linked cutover procedure.
- Execution slot, durable queue turns, and worker heartbeat tables serve different
  purposes: capacity, ordering, and telemetry. A stale heartbeat cannot free a slot.
- Fills and Closed Trades use per-run sequence keys and parent cascades.
  Stored closed-trade direction is required and constrained to `long` / `short`.

## Verification

Validate schema/aggregate behavior against a local database; use the live migration
checks in [commands](../docs/agent/COMMANDS.md#live-storage-verification).
Run accessor and affected consumer tests when query semantics change.

Raw M1 Candles retain their `(symbol_id, timestamp_utc)` primary key. Historical
correction uses native upsert without a schema change. Compression needs
TimescaleDB 2.11+ / PostgreSQL 14+ for this DML. Read
[Candle persistence](../docs/contracts/candles.md) for replay and aggregate-refresh
semantics and isolated live verification. Existing aggregate policies have rolling
windows: corrections older than those windows need an explicit materialized-bucket
refresh to appear in higher Timeframes.

## Pending recovery

**Pending recovery** means unfinished history retrieval for a logical
Market/account/M1 source. It is not general historical completeness. For source
identity, conditional progress/completion and protected startup obligations, read
the [recovery contract](../docs/contracts/recovery.md).

**Live write guard:** the durable pre-batch confirmed boundary for an unconfirmed
live Candle write. Partial commits and lost receipts cannot hide it behind a
newer latest Candle; normal successful live writes retire it without scheduling
history. See the [guard contract](../docs/contracts/recovery.md#durable-live-write-guards).

V023 classifies existing Markets as Custom and adds immutable broker source
bindings. Database constraints reject incomplete or mixed bindings, and the
source-preservation trigger prevents changing a broker instrument under existing
Candles. New broker Markets record a minute-aligned live activation boundary;
no existing data is deleted or automatically connected to a broker.

V024 persists historical download requests separately from Markets and recovery.
A partial unique index permits one queued/downloading request per Market. Immutable
request snapshots, owner/lease constraints, and the Market deletion trigger protect
accepted work. Page inserts and progress are committed together by the accessor;
aggregate refresh must finish before a request is marked completed.
