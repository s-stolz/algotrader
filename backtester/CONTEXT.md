# Backtester Context

Standalone Python backtesting module for historical candle simulation.

## Domain Vocabulary

- **Trade Direction**: simulated trade orientation, either `long` or `short`.
  Avoid using direction-neutral terms such as exposure when discussing user-facing
  backtest behavior.
- **Allowed Directions**: backtest configuration that limits which Trade
  Directions a strategy may open. The canonical values are `long_only`,
  `short_only`, and `long_and_short`. Engine validation rejects targets outside
  the allowed directions instead of silently clamping them. This is the sole
  direction constraint; strategies should not carry a separate direction flag for
  the same decision. Direction validation applies to resulting Signed Target
  Quantity, not fill side.
- **Signed Target Quantity**: strategy output where positive quantity means a
  long target, zero means flat, and negative quantity means a short target.
- **Signed Portfolio Quantity**: open simulated quantity in portfolio snapshots.
  Positive values are long positions, negative values are short positions, and
  zero is flat.
- **Strategy Signal**: direction intent from a strategy. In short-capable
  backtests, positive means target long, zero means hold the current target, and
  negative means target short; in long-only backtests, negative means return to
  flat.
- **Direction-Neutral Strategy**: a strategy whose signals can be interpreted
  under any Allowed Directions mode. The built-in SMA crossover strategy uses
  bullish crossover for long intent and bearish crossunder for short intent or
  flat exit depending on Allowed Directions: `long_only` maps bearish crossunder
  to flat, `short_only` maps bullish crossover to flat, and `long_and_short`
  reverses between long and short. Exit-to-flat signals while already flat are
  idempotent and do not emit fills or closed trades.
- **Flat Target**: a Signed Target Quantity of zero. Short-capable strategies use
  Flat Targets when they need to exit to cash instead of reversing direction.
- **Position Reduction**: a Signed Target Quantity change that reduces but does
  not reverse an open simulated trade. Position Reduction is distinct from a
  partial fill; the requested target delta still fills completely or not at all.
- **Short Cover**: a buy fill that reduces or closes a Short Trade. A Short
  Cover moves Signed Portfolio Quantity from negative toward zero; it is not a
  temporary long position.
- **Direction Flip**: a Signed Target Quantity change that crosses through flat
  between long and short. The fill may be one execution delta, but closed trade
  records remain separate round trips; a flip from `+1` to `-1` is one sell fill
  of quantity `2`, not two fill records.
- **Short Trade**: a simulated Backtest Closed Trade with `short` Trade
  Direction. A short trade is opened by a sell fill and closed by a buy fill.
- **Closed Trade Direction**: explicit Trade Direction stored on a Backtest
  Closed Trade. Consumers should read this value instead of inferring direction
  from fill order. Fill records keep execution side only and do not carry Trade
  Direction because a Direction Flip fill can both close and open trades.
- **Closed Trade Quantity**: positive absolute size of a completed trade.
  Realized PnL uses Closed Trade Direction: long trades use exit minus entry;
  short trades use entry minus exit; fees reduce both.
- **Direction Breakdown Metrics**: backtest metrics split by Closed Trade
  Direction. The first short-support slice reports long and short trade counts,
  win rates, and realized PnL totals using flat metric keys
  `long_trade_count`, `short_trade_count`, `long_win_rate_pct`,
  `short_win_rate_pct`, `long_realized_pnl`, and `short_realized_pnl`.
  Direction win rates are `0.0` when there are no trades in that direction.
  Existing `trade_count` remains the total closed-trade count across directions.
- **Flip Fee Allocation**: fee assignment for a Direction Flip. Fees are split
  pro rata by quantity between the closing trade and the newly opened opposite
  trade.
- **Short Protective Exit**: stop-loss or take-profit level for a Short Trade.
  The stop-loss is above entry, the take-profit is below entry, and ambiguous
  same-bar stop-vs-target behavior follows the run's intrabar exit policy. A
  short entry at `100` with `stop_loss_pct=5` and `take_profit_pct=10` has
  planned prices `105` and `90`.
- **Protective Exit Reset**: a stop-loss or take-profit exit resets the desired
  target to flat. Re-entry requires a later strategy signal or target change.

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
- `src/app/backtest_runs.py`: deterministic asynchronous submission validation,
  durable run retrieval/history, execution-log reads, and terminal-only deletion.
- `src/app/backtest_worker.py`: singleton FIFO polling, conditional claiming,
  child-process execution, and successful completion persistence.
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
- `main.py`: backtester API process entrypoint.
- `worker.py`: singleton asynchronous worker process entrypoint.
- `smoke.py`: deployed success/failure lifecycle smoke check.

## Contracts

- Run with `PYTHONPATH=src` when invoking tests or local modules directly.
- `BacktestRequest` selects engine, symbols, timeframe, start/end, strategy,
  execution config, initial capital, exchange, and data granularity.
- `ExecutionConfig.allowed_directions` is the canonical request field for
  Allowed Directions, with values `long_only`, `short_only`, and
  `long_and_short`. When omitted or default-constructed, the value is
  `long_and_short`.
- CLI runs expose Allowed Directions through `--allowed-directions`, defaulting
  to `long_and_short`.
- Version 2 request snapshots replace legacy `allow_short` with Allowed
  Directions. New submissions use Allowed Directions only, and immutable request
  snapshots always materialize the resolved `allowed_directions` value.
- Request schema version 2 adoption assumes local durable backtest data can be
  cleaned before rollout; runtime code does not need to backfill legacy
  `allow_short` request snapshots.
- Durable lifecycle values are `queued`, `running`, `succeeded`, and `failed`.
  The backtester owns lifecycle policy; database-accessor-api exposes storage
  primitives.
- `POST /backtests` validates deterministic request rules without loading market
  data or invoking an engine, persists a queued immutable request, and returns
  `202 Accepted` with `Location: /backtests/{run_id}`.
- `GET /backtests/{run_id}` returns epoch-millisecond lifecycle timestamps and
  state-specific fields: no artifacts while queued/running, metrics and
  diagnostics when succeeded, and bounded sanitized errors when failed.
- `GET /backtests` accepts optional status, symbol, timeframe, strategy, engine,
  `submitted_from_ms`, and `submitted_to_ms` filters. It returns all matches in
  storage-provided newest-first order without pagination. It does not filter by
  Allowed Directions in the first short-support slice.
- `GET /backtests/{run_id}/fills` and `/trades` return separate execution-log
  collections in storage-provided sequence order. Existing runs with no artifacts
  return empty lists; missing runs return not found.
- `DELETE /backtests/{run_id}` permits only `succeeded` and `failed` runs.
  Queued and running runs return a conflict because deletion is not cancellation.
- `GET /health` reports API process readiness for the local stack healthcheck.
- `BacktestRunLifecyclePersistenceAdapter` maps domain status enums and completed
  results to conditional lifecycle updates and atomic successful completion.
  Completion payloads include metrics, diagnostics, fills, and closed trades,
  but never the equity curve.
- Backtest result schema version 3 is the only accepted completed-result schema.
  Closed trade artifacts include nullable `stop_loss_price` and
  `take_profit_price` planned levels plus required closed-trade Trade Direction.
- The singleton worker selects queued runs by `(submitted_at_ms, run_id)`, refreshes
  the queue after a lost conditional claim, and executes at most one claimed run
  at a time.
- Claimed requests execute in a spawned child process from their immutable
  snapshot. Child output is compact and excludes the equity curve; only the
  worker parent persists lifecycle and result state.
- Child-reported execution failures and abnormal child exits become sanitized,
  bounded failed-run records. Detailed exception tracebacks remain in worker
  logs and failed runs persist no result artifacts.
- Worker startup conditionally marks pre-existing running records failed with
  `worker_interrupted` before claiming queued work. Terminal persistence errors
  are logged and terminate the worker without retry so restart reconciliation
  can resolve the still-running record.
- Successful synchronous CLI persistence creates a terminal `succeeded` run using
  the versioned request/result contract and normalized fill/trade payloads.
- Current parity slice is single-symbol bar-mode for vectorized and event-driven
  engines.
- Docker Compose runs `backtester-api` and one `backtester-worker` service from
  the same image. The worker reads `BACKTESTER_WORKER_POLL_INTERVAL_SECONDS`,
  defaults to one second, and processes one run at a time.
- Candle input normalizes root `CONTEXT.md` candle fields plus `symbol`.
- Declarative bar strategies may attach `ProtectiveExitSpec.stop_loss_pct` or
  `take_profit_pct`; long protective exits are active on the entry fill bar,
  gap-through exits fill at the bar open, ambiguous stop-vs-target bars use
  `ExecutionConfig.intrabar_exit_policy` with conservative stop-first default,
  and closed trades report the matching stop-loss or take-profit exit reason.
  Short protective exits mirror long exits with stop-loss above entry and
  take-profit below entry.
- Closed `Trade` results include Trade Direction and `exit_reason` using
  `signal`, `stop_loss`, or `take_profit`; signal-only exits default to `signal`
  and persistence payloads preserve the value.
- Closed `Trade` results may include nullable `stop_loss_price` and
  `take_profit_price` planned protective exit levels. These values describe the
  protective levels active for the trade, not necessarily the actual exit price.
- Metrics include Direction Breakdown Metrics for long and short closed trades.
- Protective-exit diagnostics remain aggregate counts across directions and
  include both long exits and short covers; metrics own the long/short
  breakdown.
- `signal_exit_count` counts signal-driven exit fills across directions,
  including long exits and short covers, and does not count raw exit signals that
  emit no fill.

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
- Short-support tests treat `long_and_short` as the primary/default behavior and
  cover `long_only` and `short_only` as current supported modes, not legacy
  compatibility paths.
- Deployed asynchronous workflow: start the stack, then run
  `make smoke-backtester`.
- Run shared client or indicator engine tests when data loading or indicator
  integration changes.
