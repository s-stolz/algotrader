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
- Legacy baseline detection may record only V001–V002. V003/V004 must execute:
  compression, policy, and historical-refresh effects cannot all be inferred
  from catalog state. V005 upgrades compatible legacy closed-trade tables and
  rejects populated directionless tables; V006 audits the complete structure.
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
  requests and fixed membership; whole-batch deletion cascades while direct member
  deletion remains guarded.
- Lifecycle fields are normalized; versioned request/result documents and nullable
  replay metadata use JSONB. Schema-version changes do not necessarily require
  SQL changes. Preserve historical rows without manufacturing missing metadata.
- Execution slot, durable queue turns, and worker heartbeat tables serve different
  purposes: capacity, ordering, and telemetry. A stale heartbeat cannot free a slot.
- Fills and Closed Trades use per-run sequence keys and parent cascades.
  Stored closed-trade direction is required and constrained to `long` / `short`.

## Verification

Validate schema/aggregate behavior against a local database; use the live migration
checks in [commands](../docs/agent/COMMANDS.md#live-storage-verification).
Run accessor and affected consumer tests when query semantics change.
