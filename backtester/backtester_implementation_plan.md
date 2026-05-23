# Backtester Implementation Plan

This document is historical migration context for incremental delivery.
Target architecture is defined in `backtester_design.md`.

## Ralph Planning Status

Ralph PRDs/issues are the active source of truth for new implementation campaigns.
This file preserves the original milestone breakdown so completed baseline work and
remaining roadmap candidates stay understandable, but new work should be planned in
Ralph artifacts rather than by extending this document directly.
Agents should read this only when historical sequencing or deferred scope is
needed for a backtester task.

- M0-M3 are completed baseline work and should not be redone.
- The Ralph PRD `backtester-bar-engine-parity` covered single-symbol, bar-mode
  vectorized/event-driven parity: request-level engine selection, mandatory strategy
  resolution, declarative SMA crossover support, event-driven bar execution, shared
  fill/accounting semantics, CLI engine selection, and parity/no-lookahead coverage.
- Future PRD candidates include persistence, FastAPI start/query surfaces, research
  ergonomics and sweeps, richer order realism, tick support, multi-symbol runs, and
  multi-timeframe parallelism.

## Delivery Rules

1. Every milestone must end with runnable code.
2. Every milestone must end with passing tests in its scope.
3. Prefer vertical slices over horizontal layer-first implementation.
4. Start with fewer modules; split only when code growth requires it.
5. Keep one source of truth for shared types in `domain/types.py`.
6. Do not implement tick support before bar-mode parity is stable.
7. CLI and FastAPI must call the same app-layer orchestration.
8. Keep Ralph PRDs/issues updated during delivery; keep this plan as historical context.
9. `engines/vectorized.py` must be true array-based runtime (no per-bar `StrategyInput`/`StrategyState` interpreter loop).
10. `StrategyInput` and `StrategyState` are event-driven runtime concepts; vectorized mode evaluates arrays/masks/targets directly and only maps outputs into shared result contracts where required.

## Current Coverage Baseline

Historical automated-test baseline before the Ralph parity campaign:

- `backtester`: legacy tests plus M0 skeleton coverage (`tests/signals/test_signals.py`, `tests/portfolio/test_portfolio.py`, `tests/test_skeleton_imports.py`, `tests/test_domain_types.py`, `tests/test_strategy_base.py`).
- `libs/db_accessor_client`: unit tests for current market/candle client endpoints.
- `database-accessor-api`: currently no automated tests.

Historical high-priority gaps from the original plan:

- M0 coverage exists for package imports and minimal contracts; execution/data/engine/adapters/reporting behavior coverage still missing
- no vectorized vs event-driven parity tests
- no persistence flow smoke test
- no FastAPI adapter route tests for backtest start/query

## Milestone Template

Each milestone defines:

- Goal
- In scope
- Out of scope
- Deliverables
- Executable path
- Test coverage
- Acceptance criteria
- Deferred follow-ups

---

## M0: :checkmark: Skeleton + Minimal Types

### Goal

Create the simplified package skeleton and minimal domain contracts to support the first runnable vectorized bar slice.

### In Scope

- package layout under `backtester/src/` using the simplified domains:
  - `app`, `domain`, `execution`, `engines`, `data`, `strategies`, `adapters`, `reporting`
- mirrored test layout under `tests/`
- flattened top-level module imports (`PYTHONPATH=src`, e.g. `from domain.types import ...`)
- minimal `domain/types.py`, `domain/enums.py`, `domain/events.py`
- minimal `app/config.py`
- minimal `strategies/base.py`

### Out of Scope

- real execution logic
- real data integration
- persistence
- FastAPI

### Deliverables

- importable package skeleton
- minimal types compile and can be constructed

### Executable Path

- smoke test imports package and creates core request/result type instances

### Test Coverage

- type construction tests
- skeleton import tests

### Acceptance Criteria

- package imports cleanly
- tests pass
- no duplicate ownership of core types outside `domain/types.py`

### Deferred Follow-ups

- first runnable backtest flow

---

## M1: :checkmark: Minimal Vectorized Bar Backtest (Fixture Data)

### Goal

Deliver the first end-to-end runnable **true vectorized** backtest using fixture bar data.

### In Scope

- `engines/vectorized.py`
- vectorized runtime stages in engine:
  - feature arrays
  - condition masks
  - signal masks
  - target quantity arrays
  - vectorized execution/accounting arrays
- `StrategyInput` / `StrategyState` are not primary execution abstractions in vectorized mode.
- minimal shared execution modules:
  - `execution/portfolio.py`
  - `execution/fills.py`
  - `execution/sizing.py`
  - `execution/risk.py`
  - `execution/trades.py`
- `strategies/conditions.py` helpers (`crossover`, `crossunder`)
- `strategies/examples/sma_crossover.py`
- `app/backtest_runner.py` (single-run orchestration)
- minimal `reporting/metrics.py`

### Out of Scope

- `data/*` real fetch path
- `adapters/*`
- event-driven engine
- persistence/API

### Deliverables

- runnable vectorized fixture backtest
- fills, trades, equity path, minimal summary metrics
- no per-bar strategy-runtime interpreter dependency in vectorized path

### Executable Path

- run SMA crossover on fixture bars and return `BacktestResult`

### Test Coverage

- integration test: fixture bars -> result
- unit tests: fill timing, trade lifecycle, portfolio updates, strategy condition helpers
- guard test: vectorized engine runs with `DataFrame.iterrows`/`itertuples` patched to raise

### Acceptance Criteria

- deterministic repeated output on same fixture
- result schema produced by real execution path
- vectorized implementation remains array-native under guard tests

### Deferred Follow-ups

- real data + indicator integration

---

## M2: :checkmark: Real Data + Indicator Integration (Vectorized)

### Goal

Replace fixture-only inputs with real historical data and shared indicator engine integration, and
ship a minimal CLI path for running a single strategy backtest easily.

### In Scope

- `data/market_data.py`
- `data/normalization.py`
- `data/warmup.py`
- `data/indicators.py`
- `adapters/db_accessor.py` (historical fetch path)
- vectorized engine wiring to real fetch + indicator outputs into `FeatureMatrix`
- deterministic warmup/feature-completeness trimming
- `cli.py` basic command surface:
  - one-run backtest command (single symbol, bar mode)
  - strategy choice limited to shipped example strategy/strategies in this milestone (minimum:
    `sma_crossover`)
  - command delegates into app-layer orchestration (`app/backtest_runner.py`)
  - stdout summary output (metrics + fill/trade counts)

### Out of Scope

- event-driven engine
- persistence
- FastAPI
- advanced CLI UX (parameter sweeps, rich output formats, presets)

### Deliverables

- vectorized run on real symbol/time range
- warmup + trimming path in production flow
- basic CLI command that runs a backtest end-to-end without editing Python files

### Executable Path

- run SMA crossover on fetched data from db accessor adapter
- run same scenario through CLI command and receive summary output

### Test Coverage

- adapter contract tests for historical fetch mapping
- integration tests: fetch -> normalize -> indicators -> vectorized run
- trimming behavior tests
- CLI integration/smoke test:
  - argument parsing + request mapping
  - CLI command executes one run through app-layer runner

### Acceptance Criteria

- real-data vectorized run succeeds end-to-end
- warmup trimming deterministic and repeatable
- basic CLI run succeeds with deterministic output for same input

### Deferred Follow-ups

- baseline hardening and parity prep

---

## M3: :checkmark: Vectorized Baseline Hardening

### Goal

Make vectorized bar mode stable enough to be parity baseline.

### In Scope

- finalize v1 execution semantics in `execution/fills.py`:
  - decision at close `t`, earliest fill `t+1`
  - next-bar-open timestamp rule
  - gap policy (`expire` / `skip` / `error`)
- baseline fee model in `execution/fills.py` or `execution/costs.py` (simple deterministic v1 baseline;
  prefer `commission_bps` or fixed-per-trade)
- baseline slippage model in `execution/fills.py` or `execution/costs.py` (simple deterministic v1
  baseline; prefer `slippage_bps` or fixed spread-like adjustment)
- deterministic application of costs to:
  - fills
  - realized PnL
  - equity curve
  - trade records
- baseline sizing/risk behavior in `execution/sizing.py` and `execution/risk.py`
- average-cost accounting and flip handling stability
- diagnostics payload in `BacktestResult` (kept simple; no extra module split yet)
- explicit vectorized runtime guard coverage (no row-interpreter regressions)
- tests for zero-cost vs non-zero-cost runs

### Out of Scope

- event-driven engine
- persistence/API
- tick support
- liquidity-aware slippage
- symbol-specific complex fee tables
- volatility-based slippage
- partial-fill-dependent costs

### Deliverables

- stable vectorized bar baseline contract

### Executable Path

- deterministic vectorized runs across normal + gap/warmup scenarios

### Test Coverage

- unit tests for gap policy, sizing, risk, accounting
- unit tests for fee application
- unit tests for slippage application
- integration tests for warmup/gap/timestamp semantics
- integration tests for zero-cost vs post-cost result differences
- regression guard tests for vectorized array runtime (no per-bar interpreter usage)

### Acceptance Criteria

- deterministic outputs across repeated runs
- baseline semantics locked by tests
- fee/slippage semantics are fixed and covered by tests
- repeated runs with same inputs produce identical post-cost results
- event-driven parity target for M4/M5 includes matching cost behavior

### Deferred Follow-ups

- event-driven implementation

---

## M4: Minimal Event-Driven Bar Backtest

Ralph status: implemented as part of `backtester-bar-engine-parity` for single-symbol
bar-mode parity. Future event-driven expansion should be covered by later Ralph PRDs.
The initial M4/M5 parity slice proved the public contract first; it streamed
event-driven strategy decisions but still reused array-style fill generation and
portfolio accounting to match the vectorized baseline quickly. The later Ralph PRD
`backtester-sequential-event-engine` replaced that shortcut for event-driven mode.

### Goal

Implement first runnable event-driven bar engine using shared domain/execution modules.

### In Scope

- `engines/event_driven.py`
- deterministic sequential event queue using `domain/events.py` BAR events
- event-driven path:
  - v1 declarative strategy signal -> desired target -> pending target delta -> next-open fill
- reuse shared `execution/*`, `strategies/*`, `domain/types.py`
- reuse M3 baseline fee/slippage semantics as-is (no new cost logic in M4)

### Out of Scope

- generalized event bus framework
- persistence/API
- tick support

### Deliverables

- runnable event-driven backtest for same SMA scenario

### Executable Path

- run SMA scenario in event-driven mode

### Test Coverage

- integration tests: event loop + order/fill path
- basic parity checks against vectorized baseline scenarios, including cost behavior

### Acceptance Criteria

- event-driven run succeeds end-to-end
- no divergence from shared contract without explicit deviation log entry

### Deferred Follow-ups

- parity stabilization

---

## M5: Bar-Mode Parity Stabilization

Ralph status: implemented as part of `backtester-bar-engine-parity` for supported
single-symbol declarative bar strategies. Any broader parity matrix belongs in later
Ralph PRDs. The historical M5 implementation locked public parity while the
event-driven engine still leaned on vectorized-style fill/accounting helpers; that
implementation shortcut is no longer part of event-driven mode after
`backtester-sequential-event-engine`.

### Goal

Lock parity between vectorized and event-driven engines for supported **shared** v1 bar semantics.

### In Scope

- expanded parity scenario matrix
- parity scope explicitly limited to strategies that implement both vectorized and event-driven contracts
- warmup/trimming parity
- fill timestamp parity
- gap-policy parity
- post-cost parity for fills, realized PnL, equity curve, and trade records
- reuse M3 baseline fee/slippage models only (no new cost logic in M5)
- comparison tolerances policy (only where exact equality is not required)

### Out of Scope

- new feature expansion unrelated to parity
- persistence/API
- tick support

### Deliverables

- stable parity baseline

### Executable Path

- parity runner executes both engines and reports pass/fail

### Test Coverage

- parity test suite in `tests/engines/`

### Acceptance Criteria

- agreed parity suite passes, including matching baseline cost behavior
- parity regressions block new feature work

### Deferred Follow-ups

- persistence + API surfaces

---

## M5A: Sequential Event-Driven Bar Runtime

Ralph status: implemented as part of `backtester-sequential-event-engine` for the
single-symbol v1 declarative bar parity slice.

### Goal

Replace the M4/M5 event-driven array execution shortcut with an explicit
bootstrap phase and a true sequential tradable bar loop while preserving baseline
public parity with vectorized mode for supported shared semantics.

### In Scope

- `engines/event_driven.py`
- pre-start bootstrap through `EventDrivenFeatureStream`
- strict indicator warmup precondition before `start_ms`
- no-indicator strategies starting immediately at `start_ms`
- tradable loop over `[start_ms, end_ms)` only
- pending target-delta execution at the next valid in-window open
- sequential cash, actual position, desired target, fills, and end-of-bar snapshots
- gap policies `skip`, `expire`, and `error`
- final-bar pending-delta expiration when no in-window next open exists
- diagnostics produced by the sequential runtime
- public parity for fills, trades, equity curve, metrics, fees, and slippage under
  supported v1 baseline semantics

### Out of Scope

- callback strategy migration
- tick simulation
- multi-symbol or multi-timeframe synchronized event loops
- partial fills
- short support
- limit orders, stop orders, latency, spread/liquidity, queue position, or other
  richer order realism
- broad OHLCV data-health auditing
- changing vectorized engine architecture

### Runtime Notes

- Bootstrap bars are historical context only. They prepare indicator state and may
  update the previous complete feature snapshot, but they do not create signals,
  target changes, pending orders, fills, trades, or equity snapshots.
- Indicator strategies fail with an insufficient-warmup error if pre-start history
  cannot produce a complete feature snapshot before the first tradable bar.
- The tradable loop contains no warmup skip behavior. Invalid feature output after
  a successful bootstrap is a runtime error.
- Event-driven mode no longer calls the target-array fill generator or the
  vectorized cumulative-sum portfolio accounting helper. Vectorized mode continues
  to use those array helpers.

### Test Coverage

- event-driven bootstrap contract and insufficient-warmup tests
- first-tradable-bar crossover/crossunder tests using the last bootstrap snapshot
- next-open/no-lookahead and final-bar-expiration tests
- gap `skip`, `expire`, `error`, and deferred-delta netting tests
- parity tests against vectorized public results under supported shared semantics
- static guard coverage preventing event-driven reuse of array fill/accounting helpers

### Acceptance Criteria

- event-driven public baseline results match vectorized results for supported shared semantics
- bootstrap is explicit and produces no public execution artifacts
- indicator warmup failures are clear
- event-driven implementation is sequential rather than array-execution-backed

### Deferred Follow-ups

- richer event-driven bar execution
- future public callback/stateful strategy contract
- tick support

---

## M6: Persistence Foundation (DB + Accessor Stack)

Ralph status: future PRD candidate.

### Goal

Add optional persistence for backtest runs/results/trades/hyperparameters using existing DB and accessor stack.

### In Scope

- DB schema extension for backtest persistence tables
- `database-accessor-api` extension:
  - create run
  - list/query runs
  - get one run/result
  - get trades for run
- `libs/db_accessor_client` extension for typed methods
- `adapters/persistence.py`
- `adapters/db_accessor.py` persistence-query wiring
- `persist_result` flow from `BacktestRequest`

### Out of Scope

- FastAPI orchestration endpoints in backtester
- distributed job queue
- tick support

### Deliverables

- optional persistence in runnable backtests
- persisted runs retrievable through adapter/client path

### Executable Path

- run backtest with `persist_result=true`, then query run + trades

### Test Coverage

- DB accessor API integration tests for new backtest endpoints
- client contract tests for new methods
- backtester integration test for persist-on-run flow

### Acceptance Criteria

- persistence remains optional
- retrieved data matches stored run payload/trades deterministically

### Deferred Follow-ups

- FastAPI adapter endpoints

---

## M7: FastAPI Adapter for Backtest Start/Query

Ralph status: future PRD candidate.

### Goal

Expose start/query operations through FastAPI next to CLI without duplicating orchestration logic.

### In Scope

- `adapters/api/main.py`
- `adapters/api/dependencies.py`
- `adapters/api/schemas.py`
- `adapters/api/routes/backtests.py`
- endpoints:
  - start backtest
  - list/query runs
  - get run/result
  - get run trades
- route handlers delegate to app-layer orchestration (`app/backtest_runner.py`, `app/experiment_runner.py`)

### Out of Scope

- distributed scheduling
- multi-tenant auth
- tick support

### Deliverables

- runnable FastAPI service for backtest operations

### Executable Path

- start and query backtests via FastAPI

### Test Coverage

- API integration tests for start/list/get/trades
- schema serialization tests
- tests proving CLI/API share same app orchestration behavior

### Acceptance Criteria

- all required operations available via CLI and FastAPI
- persisted retrieval works through API

### Deferred Follow-ups

- ergonomics and parameter-sweep UX over API

---

## M8: Research Ergonomics

Ralph status: future PRD candidate for sweeps and research workflow improvements.

### Goal

Improve day-to-day usability for strategy research.

### In Scope

- `app/experiment_runner.py` enhancements
- deterministic parameter sweep support
- output serialization/reporting improvements
- CLI polish on top of M2 baseline command (ergonomics, richer output formats, sweep-friendly UX)
- docs for adding custom strategies
- add one additional example strategy

### Out of Scope

- tick support
- advanced event-driven realism

### Deliverables

- reproducible sweep workflow with stable output artifacts

### Executable Path

- run parameter sweep and save comparable results

### Test Coverage

- integration tests for experiment runner and serialization

### Acceptance Criteria

- reproducible sweep outputs
- at least two example strategies run successfully

### Deferred Follow-ups

- richer execution realism

---

## M9: Richer Event-Driven Bar Execution

Ralph status: future PRD candidate for richer order realism.

### Goal

Increase event-driven execution realism on bar data beyond the M3 baseline cost model without breaking baseline parity mode.

### In Scope

- optional partial fills
- richer order request fields
- optional short support
- advanced fee/slippage models beyond M3 baseline
- optional spread/liquidity-aware execution costs
- symbol-specific fees where explicitly required
- partial-fill-aware costing where explicitly required

### Out of Scope

- tick support
- deep microstructure modeling

### Deliverables

- optional richer event-driven modes behind explicit config

### Executable Path

- run configurable event-driven bar simulations with richer options

### Test Coverage

- unit/integration tests per new mode
- regression tests ensuring baseline parity mode remains intact

### Acceptance Criteria

- richer modes are optional
- baseline parity mode stays unchanged

### Deferred Follow-ups

- tick support

---

## M10A: Vectorized Tick Replay (v2)

Ralph status: future PRD candidate for tick support.

### Goal

Add deterministic vectorized tick replay.

### In Scope

- `data_granularity=tick`
- tick normalization path in `data/normalization.py`
- tick indicator path in `data/indicators.py`
- vectorized tick replay execution mode

### Out of Scope

- event-driven tick loop
- exchange realism

### Deliverables

- runnable vectorized tick replay mode

### Acceptance Criteria

- deterministic replay
- no regressions to bar-mode contracts

---

## M10B: Event-Driven Tick Simulation (v2)

Ralph status: future PRD candidate for tick support.

### Goal

Add sequential event-driven tick simulation.

### In Scope

- tick events in `domain/events.py`
- event-driven tick loop in `engines/event_driven.py`
- tick-triggered execution behavior

### Out of Scope

- full microstructure/queue-position simulation unless separately specified

### Deliverables

- runnable event-driven tick mode

### Acceptance Criteria

- tick mode runs successfully
- bar-mode semantics remain stable

---

## Deviation Log

Record temporary deviations from `backtester_design.md`.

| Date | Deviation | Reason | Recovery Milestone |
| ---- | --------- | ------ | ------------------ |
| TBD  |           |        |                    |

## Rollback / Simplification Rules

1. If milestone scope is too large, cut optional features, not acceptance criteria.
2. Prefer temporary config flags over contract churn.
3. During parity stabilization, avoid contract changes unless required by failing tests.
4. If parity regresses, freeze new feature work until parity is restored.
