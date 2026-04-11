# Backtester Implementation Plan

This document defines incremental delivery.
Target architecture is defined in `backtester_design.md`.

## Delivery Rules

1. Every milestone must end with runnable code.
2. Every milestone must end with passing tests in its scope.
3. Prefer vertical slices over horizontal layer-first implementation.
4. Start with fewer modules; split only when code growth requires it.
5. Keep one source of truth for shared types in `domain/types.py`.
6. Do not implement tick support before bar-mode parity is stable.
7. CLI and FastAPI must call the same app-layer orchestration.
8. Keep this implementation plan updated during delivery; mark completed milestones with `:checkmark:`.
9. `engines/vectorized.py` must be true array-based runtime (no per-bar `StrategyInput`/`StrategyState` interpreter loop).
10. `StrategyInput` and `StrategyState` are event-driven runtime concepts; vectorized mode evaluates arrays/masks/targets directly and only maps outputs into shared result contracts where required.

## Current Coverage Baseline

Current automated tests in the repository relevant to this work:

- `backtester`: legacy tests only (`test/signals/test_signals.py`, `test/portfolio/test_portfolio.py`).
- `libs/db_accessor_client`: unit tests for current market/candle client endpoints.
- `database-accessor-api`: currently no automated tests.

Current high-priority gaps:

- no tests yet for new architecture modules in `app/domain/execution/engines/data/strategies/adapters/reporting`
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

## M0: Skeleton + Minimal Types

### Goal

Create the simplified package skeleton and minimal domain contracts to support the first runnable vectorized bar slice.

### In Scope

- package layout under `backtester/src/` using the simplified domains:
  - `app`, `domain`, `execution`, `engines`, `data`, `strategies`, `adapters`, `reporting`
- mirrored test layout under `tests/`
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

## M1: Minimal Vectorized Bar Backtest (Fixture Data)

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

## M2: Real Data + Indicator Integration (Vectorized)

### Goal

Replace fixture-only inputs with real historical data and shared indicator engine integration.

### In Scope

- `data/market_data.py`
- `data/normalization.py`
- `data/warmup.py`
- `data/indicators.py`
- `adapters/db_accessor.py` (historical fetch path)
- vectorized engine wiring to real fetch + indicator outputs into `FeatureMatrix`
- deterministic warmup/feature-completeness trimming

### Out of Scope

- event-driven engine
- persistence
- FastAPI

### Deliverables

- vectorized run on real symbol/time range
- warmup + trimming path in production flow

### Executable Path

- run SMA crossover on fetched data from db accessor adapter

### Test Coverage

- adapter contract tests for historical fetch mapping
- integration tests: fetch -> normalize -> indicators -> vectorized run
- trimming behavior tests

### Acceptance Criteria

- real-data vectorized run succeeds end-to-end
- warmup trimming deterministic and repeatable

### Deferred Follow-ups

- baseline hardening and parity prep

---

## M3: Vectorized Baseline Hardening

### Goal

Make vectorized bar mode stable enough to be parity baseline.

### In Scope

- finalize v1 execution semantics in `execution/fills.py`:
  - decision at close `t`, earliest fill `t+1`
  - next-bar-open timestamp rule
  - gap policy (`expire` / `skip` / `error`)
- baseline sizing/risk behavior in `execution/sizing.py` and `execution/risk.py`
- average-cost accounting and flip handling stability
- diagnostics payload in `BacktestResult` (kept simple; no extra module split yet)
- explicit vectorized runtime guard coverage (no row-interpreter regressions)

### Out of Scope

- event-driven engine
- persistence/API
- tick support

### Deliverables

- stable vectorized bar baseline contract

### Executable Path

- deterministic vectorized runs across normal + gap/warmup scenarios

### Test Coverage

- unit tests for gap policy, sizing, risk, accounting
- integration tests for warmup/gap/timestamp semantics
- regression guard tests for vectorized array runtime (no per-bar interpreter usage)

### Acceptance Criteria

- deterministic outputs across repeated runs
- baseline semantics locked by tests

### Deferred Follow-ups

- event-driven implementation

---

## M4: Minimal Event-Driven Bar Backtest

### Goal

Implement first runnable event-driven bar engine using shared domain/execution modules.

### In Scope

- `engines/event_driven.py`
- deterministic sequential event queue using `domain/events.py` BAR events
- event-driven path:
  - `ExecutionTarget -> OrderRequest -> Fill`
- reuse shared `execution/*`, `strategies/*`, `domain/types.py`

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
- basic parity checks against vectorized baseline scenarios

### Acceptance Criteria

- event-driven run succeeds end-to-end
- no divergence from shared contract without explicit deviation log entry

### Deferred Follow-ups

- parity stabilization

---

## M5: Bar-Mode Parity Stabilization

### Goal

Lock parity between vectorized and event-driven engines for supported **shared** v1 bar semantics.

### In Scope

- expanded parity scenario matrix
- parity scope explicitly limited to strategies that implement both vectorized and event-driven contracts
- warmup/trimming parity
- fill timestamp parity
- gap-policy parity
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

- agreed parity suite passes
- parity regressions block new feature work

### Deferred Follow-ups

- persistence + API surfaces

---

## M6: Persistence Foundation (DB + Accessor Stack)

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

### Goal

Improve day-to-day usability for strategy research.

### In Scope

- `app/experiment_runner.py` enhancements
- deterministic parameter sweep support
- output serialization/reporting improvements
- CLI polish
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

### Goal

Increase execution realism on bar data without breaking baseline parity mode.

### In Scope

- optional partial fills
- richer order request fields
- optional short support
- additional cost/risk variants when explicitly required

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
