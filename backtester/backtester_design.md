# Backtester Design Plan

This document defines the target architecture/spec (end state).
Implementation order is defined in `backtester_implementation_plan.md`.

## Architecture Rules

Use this rule set consistently:

1. `domain` = core types and pure business logic.
2. `engines` = vectorized vs event-driven execution modes.
3. `adapters` = external integrations (db accessor, persistence, API).
4. `strategies` = strategy contracts + rules + examples/custom strategies.
5. `app` = orchestration entrypoints/use cases.

Pragmatic modularity rule:

- Start with fewer modules.
- Split files only when code growth creates clear pressure.
- Avoid broad names unless the file truly owns a broad concern.

Naming rule:

- Use `domain/types.py` as the single home for shared dataclasses/entities/value objects.
- Use `domain/enums.py` for enums.
- Use `domain/events.py` for event types.
- Elsewhere, prefer singular concrete names (`portfolio.py`, `fills.py`, `sizing.py`, `risk.py`, `metrics.py`).

## Goals

Build a backtester with:

1. Vectorized engine for fast research.
2. Event-driven engine for sequential execution realism.
3. Optional persistence of backtest run metadata, hyperparameters, results, and trades in the existing DB.
4. FastAPI access for start/query workflows, next to CLI.

Reuse constraints:

- Reuse `libs/db_accessor_client`.
- Reuse `libs/indicator_engine`.
- Extend (not duplicate) `database-accessor-api` for backtest persistence/query operations.

## Pipeline

Canonical pipeline:

`Data -> Features/Indicators -> Strategy Decision -> TradingIntent -> ExecutionTarget -> Execution -> Portfolio Ledger -> Metrics -> (Optional) Persistence`

Key boundary:

- `TradingIntent` is semantic strategy output.
- `ExecutionTarget` is post-sizing/post-risk, engine-ready output.
- Event-driven mode uses per-bar runtime objects (`StrategyInput`, `StrategyState`, `TradingIntent`).
- Vectorized mode evaluates full arrays and builds target arrays directly; it does not run per-bar runtime evaluation.

## Target Package Structure

```text
backtester/
  src/
    app/
      backtest_runner.py
      experiment_runner.py
      config.py

    domain/
      types.py
      enums.py
      events.py

    execution/
      portfolio.py
      fills.py
      sizing.py
      risk.py
      trades.py

    engines/
      vectorized.py
      event_driven.py

    data/
      market_data.py
      indicators.py
      normalization.py
      warmup.py

    strategies/
      base.py
      conditions.py
      examples/
        sma_crossover.py
      custom/

    adapters/
      db_accessor.py
      persistence.py
      api/
        main.py
        dependencies.py
        schemas.py
        routes/
          backtests.py

    reporting/
      metrics.py
      serializers.py

    cli.py

  test/
    app/
    domain/
    execution/
    engines/
    data/
    strategies/
    adapters/
    reporting/
```

Import convention for this layout:

- run with `PYTHONPATH=src`
- import top-level modules directly (`from domain.types import ...`, `from strategies.base import ...`)

## Responsibility Map

- `app/backtest_runner.py`
  - Orchestrates one backtest run end-to-end.
  - Called by CLI and FastAPI.
- `app/experiment_runner.py`
  - Orchestrates parameter sweeps and experiment batches.
- `domain/types.py`
  - Canonical runtime and result dataclasses.
- `execution/`
  - Shared execution behavior for both engines.
- `engines/vectorized.py`
  - True array-based simulation path (feature arrays -> condition masks -> target arrays -> vectorized execution).
- `engines/event_driven.py`
  - Deterministic sequential event queue path.
- `data/`
  - Market-data load/normalize/warmup + indicator wiring.
- `strategies/base.py`
  - Strategy interfaces/contracts.
- `strategies/conditions.py`
  - Reusable strategy condition helpers (`crossover`, `crossunder`, etc.).
- `strategies/examples/`
  - Shipped reference strategies.
- `strategies/custom/`
  - User/project-specific strategies.
- `adapters/db_accessor.py`
  - Wrap `db_accessor_client` for data + backtest persistence APIs.
- `adapters/persistence.py`
  - Persistence-focused adapter logic (save/load runs/trades/results).
- `adapters/api/`
  - FastAPI transport layer only.
- `reporting/metrics.py`
  - Result metrics.

## Domain Contracts (In `domain/types.py`)

Minimum required types for v1:

- `BacktestRequest`
  - symbols/timeframe/start/end
  - strategy config
  - execution config
  - initial capital
  - `data_granularity` (`bar` in v1, `tick` in v2)
  - `persist_result: bool = False`
  - `run_metadata` (optional labels/tags/context)
- `ExecutionConfig`
  - `signal_timing`
  - `fill_timing`
  - `price_source`
  - `allow_partial_fills`
  - `allow_short`
  - `trade_accounting_policy`
  - `gap_policy`
- `BarView`, `TickView`, `MarketView` (v1 uses `BarView`)
- `PositionView`, `PortfolioView`
- `FeatureMatrix` / `SignalMatrix` / `ExecutionArrayBundle` (vectorized-runtime array contracts)
- `StrategyInput`
  - event-driven runtime snapshot contract
  - timestamp/symbol/market_view/features/position/portfolio
- `StrategyState`
  - event-driven runtime state contract
  - persistent per `(strategy_id, symbol)` state payload
- `TradingIntent` (semantic)
  - event-driven decision output contract
  - v1 variants: `EnterLong`, `ExitLong`, `ClosePosition`
- `ExecutionTarget` (resolved)
  - v1 variant: `SetTargetQuantity`
- `OrderRequest`
  - event-driven only
- `Fill`, `Trade`, `PortfolioSnapshot`
- `BacktestResult`
  - result payload + diagnostics + optional persistence metadata (`backtest_run_id`, `persisted_at`)
- `BacktestRunRecord`, `BacktestTradeRecord`, `BacktestQuery`
  - persistence/query-facing types

`domain/enums.py` owns policy and side enums.
`domain/events.py` owns event types (`BAR` v1, `TICK` v2).

## Strategy Contract

In `strategies/base.py`:

- `StrategyDefinition`
  - `feature_specs`
  - `decision_model` (event-driven contract)
  - `sizing_model`
  - optional `risk_rules`

Event-driven lifecycle contract:

- `decision_model` returns `(TradingIntent, next_state)`.
- No hidden mutable strategy state outside `StrategyState`.

Deterministic state sequence per timestamp `t`:

1. Build `StrategyInput`.
2. Load prior `StrategyState`.
3. Evaluate decision -> `(TradingIntent, next_state)`.
4. Persist `next_state`.
5. Resolve intent -> `ExecutionTarget`.
6. Execute.

Vectorized strategy contract:

- Vectorized engine consumes `FeatureMatrix` (aligned full-series arrays), not per-bar `StrategyInput`.
- Strategy logic is evaluated on arrays:
  1. evaluate condition masks (`ConditionEvaluator`)
  2. derive signal masks (`SignalMatrix`)
  3. build target quantity array (`PositionBuilder`)
- No per-bar `StrategyState` mutation/evaluation in vectorized runtime.

## Shared Execution Semantics

Execution flow:

`TradingIntent -> ExecutionTarget -> (OrderRequest or direct bar execution) -> Fill -> Portfolio/Trades`

Vectorized execution flow:

`FeatureMatrix -> condition masks -> signal masks -> target_qty array -> vectorized fills -> portfolio arrays -> trades`

Scope split:

- `execution/sizing.py`: sizing policies (`FixedQuantitySizer`, `PercentOfEquitySizer`).
- `execution/risk.py`: pre-trade constraints (`LongOnlyRule`, `MaxExposureRule`, etc.).
- `execution/fills.py`: intent resolution + fill policy + cost application.
- `execution/portfolio.py`: cash/equity/positions/PnL state.
- `execution/trades.py`: fill-to-trade lifecycle construction.

Hard rules:

1. `ExecutionConfig` is a domain type (not app-level).
2. Intent resolution outputs `ExecutionTarget` only.
3. Vectorized mode does not create `OrderRequest`; it creates synthetic fills directly from `ExecutionTarget` + fill policy.
4. Event-driven mode converts `ExecutionTarget -> OrderRequest -> Fill`.
5. Risk rules are applied during intent resolution (pre-trade), not re-applied post-fill.
6. Vectorized mode is not a per-bar interpreter and must not depend on per-bar `StrategyInput`/`StrategyState`.

## Engine Behavior

### Vectorized (`engines/vectorized.py`)

- Fetch normalized bars.
- Compute indicators/features in batch.
- Build aligned `FeatureMatrix`.
- Evaluate array-based strategy conditions directly on full arrays.
- Derive entry/exit masks and target quantity arrays.
- Apply vectorized fill, cost, and portfolio accounting arrays.
- Update portfolio/trades/metrics.

### Event-driven (`engines/event_driven.py`)

- Process deterministic sequential market-data events.
- v1 first-class event: `BAR`.
- On each event: indicator update, strategy input build, decision, intent resolution, order translation, fills, ledger/trades.
- v2 adds `TICK` events.

## Data Semantics

- All timestamps: UTC epoch milliseconds.
- Warmup + trimming rule:
  - After features are computed, rows missing required features are deterministically trimmed before decisions.
  - Same trimming behavior in both engines.
- Gap/open rule:
  - For `fill_timing=next_bar_open`, a valid next-bar `open` is required.
  - Missing/invalid `open` triggers configured `gap_policy` (`expire`/`skip`/`error`).

## Fill/Accounting Policy (v1 baseline)

1. No same-bar lookahead in parity baseline.
   - Decide at bar close `t`, earliest execution `t+1`.
2. For next-bar-open fills, stored fill timestamp is next bar timestamp.
3. Position accounting baseline: average cost.
4. Flips are split as close-then-open.
5. Trade records are symbol-scoped and strategy-tagged.

## Portfolio Scope (v1)

1. One strategy per backtest run.
2. Example strategies are symbol-scoped.
3. Portfolio ledger is multi-position across symbols.
4. Cross-asset synchronized decision strategies are deferred.
5. `PortfolioSnapshot` is account-level in v1.

## Persistence and API Integration

Persistence target:

- Optional DB persistence for runs/hyperparameters/results/trades.

Integration path:

1. Extend DB schema for backtest tables.
2. Extend `database-accessor-api` for create/list/get run + get trades.
3. Extend `libs/db_accessor_client` with typed methods.
4. Implement adapter layer in backtester (`adapters/db_accessor.py`, `adapters/persistence.py`).

Invocation surfaces:

- CLI (`cli.py`) for local/research workflows.
- FastAPI (`adapters/api/...`) for service workflows.

Single-orchestration rule:

- CLI and API must call the same app-layer use cases (`app/backtest_runner.py` / `app/experiment_runner.py`).

## Testing Structure

Tests mirror source structure:

- `test/app/`
- `test/domain/`
- `test/execution/`
- `test/engines/`
- `test/data/`
- `test/strategies/`
- `test/adapters/`
- `test/reporting/`

Required test priorities:

1. Core execution correctness (highest priority):
   - no-lookahead enforcement
   - fill timestamp semantics
   - warmup/trimming behavior
   - gap-policy behavior
   - strategy-state lifecycle determinism
   - portfolio/trade accounting invariants
   - vectorized no-interpreter constraint (`iterrows`/per-bar runtime not used)
2. Engine parity:
   - vectorized vs event-driven parity on supported shared strategy semantics
3. Adapter boundary tests (thin and contract-focused):
   - keep these only for mapping/serialization/error-translation behavior in `adapters/*`
   - do not build heavy duplicate tests for pure pass-through wrappers already covered elsewhere
4. Persistence/API smoke path (minimal but required):
   - one end-to-end persisted run (`persist_result=true`) and successful retrieval of run/trades via API
5. Reporting/sweep reproducibility:
   - stable metrics/serialization shape and deterministic experiment outputs

## Scope and Sequencing Note

- This design plan defines architecture and contracts only.
- Non-goals, roadmap items, and version/sequencing decisions are tracked in `backtester_implementation_plan.md`.
