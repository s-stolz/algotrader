# ADR-0006: Use Ledgered TimescaleDB Migrations

Status: Accepted

Date: 2026-07-08

## Context

AlgoTrader currently stores TimescaleDB bootstrap SQL in `timescaledb-init/`,
which Docker runs only when a database volume is first created. Some setup SQL is
idempotent, but rerunning setup files is not the same as knowing which schema
changes have already been applied.

## Decision

Use forward-only, ledgered TimescaleDB migrations under
`timescaledb-init/migrations/` with strict `VNNN__description.sql` filenames.
`make migrate-db` will run a Python migration runner through the existing
generated configuration and execute SQL inside the `timescaledb` Docker
container. Applied migrations are recorded with checksums in `schema_migrations`;
already-applied checksum drift, missing files, gaps, and duplicate versions fail
the run. Existing databases that match the historical schema may conservatively
baseline `V001`-`V002`; `V003` and `V004` are always replayed because their
policy/compression and historical-refresh effects cannot all be inferred from
catalog state. No version after `V002` is included in this legacy baseline.

## Consequences

- Fresh Docker volumes still bootstrap from `timescaledb-init/`, but ongoing
  schema changes are tracked by the migration ledger.
- Migration files are transactional per file where PostgreSQL allows it and stop
  the run on first failure.
- Rollbacks are not modeled; reversions use later forward migrations.
- A session-scoped database advisory lock prevents concurrent migration runners
  from applying schema changes at the same time and is released automatically if
  the runner's PostgreSQL session ends unexpectedly.
- `V005` upgrades compatible empty legacy closed-trade tables and rejects
  populated directionless or structurally unsupported tables with recovery
  guidance instead of recording a silently incomplete schema.

## References

- `timescaledb-init/CONTEXT.md`
- `timescaledb-init/migrations/`
- `scripts/migrate_db.py`
- `Makefile`
