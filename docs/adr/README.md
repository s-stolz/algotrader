# Architecture Decision Records

Use ADRs for durable decisions that future agents should not re-litigate during
normal implementation work. Keep each ADR small and focused on one decision.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-layered-agent-context.md) | Accepted | Layer agent context by read cost and task relevance. |
| [0002](0002-root-context-owns-cross-service-contracts.md) | Accepted | Root `CONTEXT.md` owns cross-service contract summaries. |
| [0003](0003-generated-runtime-configuration.md) | Accepted | Runtime env files are generated from tracked topology and local secrets. |
| [0004](0004-python-typecheck-verify-gate.md) | Accepted | Python Pyright checks are a strict verify gate. |
| [0005](0005-backtester-owns-durable-run-lifecycle.md) | Accepted | Backtester owns durable run lifecycle policy over database accessor storage primitives. |
| [0006](0006-ledgered-timescaledb-migrations.md) | Accepted | TimescaleDB schema changes use forward-only ledgered migrations. |
| [0007](0007-backtest-execution-slot-requires-verified-recovery.md) | Accepted | A durable backtest slot requires verified operator recovery after uncertain exit. |

## When To Add An ADR

Add an ADR when a durable choice has a meaningful trade-off and its rationale
would be hard to infer later. Record the alternatives and consequences that
future changes must consider. Routine implementation, temporary sequencing, and
facts already clear from code or local context belong with their existing owner.

## Template

Use [TEMPLATE.md](TEMPLATE.md) for new ADRs.
