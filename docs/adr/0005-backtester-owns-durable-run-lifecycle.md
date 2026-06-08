# ADR-0005: Backtester Owns Durable Run Lifecycle

Status: Accepted

Date: 2026-06-08

## Context

Long-running backtests need durable queued, running, succeeded, and failed state.
The state must survive backtester API and worker process restarts, while the
database accessor remains reusable storage infrastructure rather than a scheduler.
Historical execution must also retain the exact request instead of rebuilding it
from application defaults that may change.

## Decision

Backtester domain types are the canonical run contracts and backtester processes
own run identity, queue selection, lifecycle transitions, and execution policy.
Database-accessor-api exposes primitive persistence operations and stores the
caller-supplied lifecycle state.

Each run stores normalized lifecycle columns and one immutable, versioned request
JSONB document. Successful result metrics and diagnostics are nullable versioned
JSONB documents. Fills and closed trades are normalized child rows with stable
per-run sequence values. PostgreSQL/TimescaleDB is the durable source of truth.

## Consequences

- Workers can recover lifecycle state without relying on API process memory.
- Request attributes are not duplicated into scalar columns or reconstructed
  from changing defaults.
- Database-accessor-api does not choose work or enforce the lifecycle graph.
- Future schema readers must branch on request/result schema versions.
- Changes to this boundary require coordinated backtester, accessor, shared
  client, Timescale, and context updates.

## References

- `CONTEXT.md`
- `backtester/CONTEXT.md`
- `database-accessor-api/CONTEXT.md`
- `timescaledb-init/CONTEXT.md`
- `libs/CONTEXT.md`
- `timescaledb-init/05-init-backtest-persistence.sql`
