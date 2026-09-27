# ADR-0007: Backtest Execution Slot Requires Verified Recovery

Status: Accepted

Date: 2026-09-26

## Context

One globally supervised backtest child may run for an unbounded normal duration.
A timeout or stale heartbeat cannot prove that an old child and its descendants
have stopped consuming capacity. Automatically stealing a lease could therefore
run two backtests at once or let a late result race restart reconciliation.

## Decision

Use one durable PostgreSQL execution-slot row. A queued-to-running claim takes
the slot in the same transaction and receives a unique owner token. Terminal
result storage checks that token and releases the slot only in the transaction
that commits the terminal state and artifacts. Failed storage, lost ownership,
or unconfirmed child exit leaves capacity occupied and records an operational
fault when storage is available. The slot has no time-based expiry.

A restarted worker reconciles interrupted running work only when the slot is
free. If an old slot remains held, an operator must stop all workers, verify
the child and descendants have exited, and clear the slot before restart. The
backtester retains lifecycle policy and queue selection; the accessor provides
conditional storage primitives under ADR-0005.

The worker uses a dedicated Linux child-subreaper supervisor per execution.
Strategy code runs in a separate spawned child; the supervisor adopts orphaned
children across process-group/session changes and confirms they are reaped with
`waitpid` before acknowledging completion. The parent requires that acknowledgement
and a clean, reaped supervisor exit. Process-group absence alone is not evidence
of descendant exit. Unsupported containment or supervisor loss keeps the slot
held instead of treating an unproven execution tree as completed.

## Consequences

- Duplicate workers cannot add capacity, and stale owner tokens cannot commit
  terminal results through the fenced settlement route.
- Asynchronous execution requires Linux subreaping and `/proc`; other hosts use
  the existing Compose worker. This favors a verifiable descendant boundary over
  an unsafe cross-platform process-group fallback.
- A crashed worker may leave the queue stopped until verified operator recovery.
  This favors execution safety over automatic availability.
- Upgrade order must stop old workers before applying the slot migration; old
  claims are then rejected by the database guard.
- Heartbeat and queue telemetry may report unavailability, but cannot free the
  slot or change durable run history.

## References

- `docs/operations/backtest-worker-recovery.md`
- `timescaledb-init/migrations/V009__backtest_execution_slot.sql`
- `backtester/CONTEXT.md`
