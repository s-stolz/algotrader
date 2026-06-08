# Backtester Context

Standalone Python backtesting module for historical candle simulation.

## Owned Interfaces

- `BacktestRequest` run configuration for engine, symbols, Timeframe, date range,
  strategy, execution config, initial capital, and data granularity.
- Shared backtest result contracts for engines, execution, portfolio, metrics, and
  reporting.
- Canonical durable run status, request snapshot, run, fill, trade, and query
  contracts.
- Strategy registry and reproducible strategy definitions.
- Candle input normalization from root `CONTEXT.md` fields plus `symbol`.

## Key Modules

- `backtester_design.md`: target architecture and active design vocabulary.
- `src/app/backtest_runner.py`: orchestration for one backtest run.
- `src/app/backtest_runs.py`: deterministic asynchronous submission validation
  and durable single-run retrieval.
- `src/domain/`: runtime dataclasses, enums, and event types.
- `src/data/`: market data loading, normalization, indicators, feature streams,
  and warmup trimming.
- `src/engines/vectorized.py`: array-based bar simulation.
- `src/engines/event_driven.py`: sequential bar-mode simulation.
- `src/execution/`: fills, portfolio, sizing, risk, and trade accounting.
- `src/strategies/`: strategy contracts, conditions, registry, and examples.
- `src/adapters/db_accessor.py`: database accessor adapter.
- `src/adapters/api/`: FastAPI submission and lifecycle-status transport.
- `src/reporting/metrics.py`: metrics from equity curve and trades.

## Contracts

- Run with `PYTHONPATH=src` when invoking tests or local modules directly.
- `BacktestRequest` selects engine, symbols, timeframe, start/end, strategy,
  execution config, initial capital, exchange, and data granularity.
- Version 1 request snapshots materialize every request field, including defaults,
  before persistence. Historical requests must not be reconstructed from current
  defaults.
- Durable lifecycle values are `queued`, `running`, `succeeded`, and `failed`.
  The backtester owns lifecycle policy; database-accessor-api exposes storage
  primitives.
- `POST /backtests` validates deterministic request rules without loading market
  data or invoking an engine, persists a queued immutable request, and returns
  `202 Accepted` with `Location: /backtests/{run_id}`.
- `GET /backtests/{run_id}` returns epoch-millisecond lifecycle timestamps and
  state-specific fields: no artifacts while queued/running, metrics and
  diagnostics when succeeded, and bounded sanitized errors when failed.
- `BacktestRunLifecyclePersistenceAdapter` maps domain status enums and completed
  results to conditional lifecycle updates and atomic successful completion.
  Completion payloads include metrics, diagnostics, fills, and closed trades,
  but never the equity curve.
- Successful synchronous CLI persistence creates a terminal `succeeded` run using
  the versioned request/result contract and normalized fill/trade payloads.
- Current parity slice is single-symbol bar-mode for vectorized and event-driven
  engines.
- Candle input normalizes root `CONTEXT.md` candle fields plus `symbol`.
- Declarative bar strategies may attach `ProtectiveExitSpec.stop_loss_pct` or
  `take_profit_pct`; long protective exits are active on the entry fill bar,
  gap-through exits fill at the bar open, ambiguous stop-vs-target bars use
  `ExecutionConfig.intrabar_exit_policy` with conservative stop-first default,
  and closed trades report the matching stop-loss or take-profit exit reason.
- Closed `Trade` results include `exit_reason` using `signal`, `stop_loss`, or
  `take_profit`; signal-only exits default to `signal` and persistence payloads
  preserve the value.

## Change Triggers

- Use `domain/types.py` and `domain/enums.py` as canonical homes for shared
  backtester concepts.
- Do not duplicate Timeframe maps if shared `db_accessor_client` can be used.
- Strategy definitions should remain explicit and reproducible through the
  strategy registry.
- Tests for `src/<area>/...` must live under the matching `tests/<area>/...`
  folder. Root-level `tests/test_*.py` files are only for root modules such as
  `cli.py` plus layout/import checks; `tests/test_layout.py` enforces this.
- Treat `backtester_implementation_plan.md` as historical roadmap context, not
  the active task queue.

## Verification

- Backtester tests: `make test backtester`.
- Run shared client or indicator engine tests when data loading or indicator
  integration changes.
