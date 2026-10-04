# Context Map

Choose the row matching the task. Read additional areas only when a changed
interface reaches them; paths in this table are relative to the repository root.

| Task | Read first |
| --- | --- |
| Charts, overlays, Workspace, UI transport | [frontend/CONTEXT.md](../frontend/CONTEXT.md) |
| WebSocket protocol, subscriptions, Redis fanout | [webserver/CONTEXT.md](../webserver/CONTEXT.md) |
| cTrader, broker commands, tick/trendbar publication | [broker-service/CONTEXT.md](../broker-service/CONTEXT.md) |
| Closed-candle ingestion, history backfill, reconnect recovery | [ingestion-service/CONTEXT.md](../ingestion-service/CONTEXT.md) |
| Market/candle queries, durable persistence transactions | [database-accessor-api/CONTEXT.md](../database-accessor-api/CONTEXT.md) |
| Historical/live indicators | [indicator-api/CONTEXT.md](../indicator-api/CONTEXT.md) |
| Simulation, strategies, execution, metrics | [backtester/CONTEXT.md](../backtester/CONTEXT.md) |
| Backtest lifecycle, batches, queue, saved-result contracts | [contracts/backtests.md](contracts/backtests.md), then affected area context |
| Shared clients, indicator computation, logging | [libs/CONTEXT.md](../libs/CONTEXT.md) |
| Topology, environment generation, ports, container resources | [config/CONTEXT.md](../config/CONTEXT.md) |
| SQL bootstrap, migrations, hypertables, aggregates | [timescaledb-init/CONTEXT.md](../timescaledb-init/CONTEXT.md) |
| Worker upgrade or held-slot recovery | [worker recovery](operations/backtest-worker-recovery.md) |
| Cross-service interface change | [contract changes](agent/CONTRACT-CHANGES.md) |
| Architecture or ownership decision | [ADR index](adr/README.md) |
| Build, run, tests | [commands](agent/COMMANDS.md) |
| Code/test conventions | [coding conventions](agent/CODING-CONVENTIONS.md) |
| Verification or documentation maintenance | [workflow](agent/WORKFLOW.md) |

## References by Purpose

- Local setup: [README](../README.md). Area READMEs explain usage; context files
  identify the seams to inspect before changing behavior.
- Strategy authoring: [STRATEGIES.md](../backtester/STRATEGIES.md).
- Engine semantics and supported scope: [backtester context](../backtester/CONTEXT.md#engine-invariants).
- Workspace acceptance evidence: [2026-09-27 acceptance](operations/backtest-workspace-v1-acceptance.md)
  and [review](operations/backtest-workspace-review-2026-09-27.md). These record
  past checks; use the recovery guide for current operating procedures.
