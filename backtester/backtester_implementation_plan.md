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

- M0-M7 and M8A, including M5A and M5B, are implemented baseline work and should
  not be redone. M6/M7 were delivered together and expanded by
  `backtester-durable-async-runs`; M8A was delivered by
  `backtester-short-trades`.
- The Ralph PRD `backtester-bar-engine-parity` covered single-symbol, bar-mode
  vectorized/event-driven parity: request-level engine selection, mandatory strategy
  resolution, declarative SMA crossover support, event-driven bar execution, shared
  fill/accounting semantics, CLI engine selection, and parity/no-lookahead coverage.
- The bracket-exit campaign added stop-loss, take-profit, and deterministic
  ambiguous-bar handling to the supported shared bar semantics.
- M8 and M9-M10B are not implemented. They remain future PRD candidates for
  research ergonomics and sweeps, richer order realism, tick support,
  multi-symbol runs, and multi-timeframe parallelism.
- M8A added explicit Allowed Directions, signed targets, symmetric long/short
  execution, short protective exits, direction-aware trade accounting and
  metrics, and durable direction fields across both bar engines.

## Delivery Rules

1. Every milestone must end with runnable code.
2. Every milestone must end with passing tests in its scope.
3. Prefer vertical slices over horizontal layer-first implementation.
4. Start with fewer modules; split only when code growth requires it.
5. Keep one source of truth for shared types in `domain/types.py`.
6. Do not implement tick support before bar-mode parity is stable.
7. CLI and worker child execution must call the same app-layer backtest
   orchestration; FastAPI submission must remain a non-executing queue boundary.
8. Keep Ralph PRDs/issues updated during delivery; keep this plan as historical context.
9. `engines/vectorized.py` must be true array-based runtime (no per-bar `StrategyInput`/`StrategyState` interpreter loop).
10. `StrategyInput` and `StrategyState` are event-driven runtime concepts; vectorized mode evaluates arrays/masks/targets directly and only maps outputs into shared result contracts where required.

## Current Coverage Baseline

Current automated coverage includes:

- Backtester domain, strategy, data preparation, execution, engine parity,
  long/short execution, bracket exits, direction-aware trade accounting,
  persistence adapters, public API routes, worker lifecycle, process isolation,
  CLI behavior, configuration, and smoke-runner tests.
- Database-accessor tests for durable JSON mapping, filters, compare-and-set
  claiming, transactional completion and rollback, execution-log ordering, and
  cascade deletion.
- Shared `db_accessor_client` tests for synchronous and asynchronous durable-run
  operations and HTTP error translation.
- A deployed smoke command covering successful and failed asynchronous lifecycle
  paths through API, worker, database accessor, and Timescale.

The standard `make test` backend gate includes the backtester,
database-accessor-api, and shared database accessor client suites.

## Milestone Status Snapshot

Current implementation snapshot:

| Milestone | Status | Current implementation note |
| --- | --- | --- |
| M0 Skeleton + Minimal Types | Implemented | Package and mirrored test layout, domain types/enums/events, config, and strategy base are present. |
| M1 Minimal Vectorized Bar Backtest | Implemented | Array-native vectorized engine, execution modules, SMA strategy, metrics, and row-iterator guard coverage are present. |
| M2 Real Data + Indicator Integration | Implemented | Historical bar adapter, normalization, indicator/warmup trimming, app orchestration, and single-run CLI are present. |
| M3 Vectorized Baseline Hardening | Implemented | Next-open semantics, gap policy, fees/slippage, sizing/risk, diagnostics, and unsupported execution guards are present. |
| M4 Minimal Event-Driven Bar Backtest | Implemented | Event-driven bar execution exists for the supported single-symbol declarative strategy slice; later superseded by M5A internals. |
| M5 Bar-Mode Parity Stabilization | Implemented | Parity tests cover supported vectorized/event-driven bar semantics, including no-lookahead and cost behavior. |
| M5A Sequential Event-Driven Bar Runtime | Implemented | Event-driven mode uses explicit bootstrap and sequential tradable-bar runtime with gap handling and helper-reuse guards. |
| M5B Bar Bracket Exits | Implemented | Stop-loss/take-profit exits, ambiguous-bar policy, exit reasons, CLI validation, parity, and persistence coverage are present. |
| M6 Durable Persistence Foundation | Implemented | Durable run schema, JSON request/result snapshots, normalized fills/trades, accessor routes, shared clients, and CLI persistence are present. |
| M7 Durable Asynchronous API and Worker | Implemented | FastAPI lifecycle API, singleton worker, FIFO claiming, child execution, terminal failure handling, and smoke coverage are present. |
| M8 Research Ergonomics | Not implemented | No experiment/sweep use case, sweep CLI/API workflow, stable sweep artifacts, custom-strategy docs, or second example strategy are present. |
| M8A Bar-Mode Short Support | Implemented | Allowed Directions and signed targets support long-only, short-only, and long/short bar runs in both engines, including flips, short protective exits, direction-aware trades and metrics, CLI/API persistence, and parity coverage. |
| M9 Richer Event-Driven Bar Execution | Not implemented | Current API and engines reject partial fills; no limit/stop order, latency, spread/liquidity, queue-position, or optional richer realism mode exists. |
| M10A Vectorized Tick Replay | Not implemented | Tick enum/view placeholders exist, but the runner and vectorized engine reject `data_granularity=tick`; no tick replay exists. |
| M10B Event-Driven Tick Simulation | Not implemented | Tick event placeholders exist, but the event-driven engine rejects tick requests; no sequential tick loop exists. |

## Milestone Template

Each milestone defines:

- Status
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

Status: Implemented.

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

## M1: Minimal Vectorized Bar Backtest (Fixture Data)

Status: Implemented.

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

Status: Implemented.

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

## M3: Vectorized Baseline Hardening

Status: Implemented.

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

Status: Implemented.

Ralph source: `backtester-bar-engine-parity` for single-symbol bar-mode parity.
Future event-driven expansion should be covered by later Ralph PRDs.
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

Status: Implemented.

Ralph source: `backtester-bar-engine-parity` for supported single-symbol
declarative bar strategies. Any broader parity matrix belongs in later Ralph
PRDs. The historical M5 implementation locked public parity while the
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

Status: Implemented.

Ralph source: `backtester-sequential-event-engine` for the single-symbol v1
declarative bar parity slice.

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

## M5B: Bar Bracket Exits

Status: Implemented.

Ralph source: `backtester-bar-bracket-exits` for the single-symbol declarative
bar parity slice.

### Goal

Add deterministic long stop-loss and take-profit exits without changing the
supported baseline engine contract.

### Implemented Scope

- optional `ProtectiveExitSpec.stop_loss_pct` and `take_profit_pct`
- entry-bar activation and gap-through fills at the bar open
- deterministic ambiguous stop/target handling through
  `ExecutionConfig.intrabar_exit_policy`
- signal, stop-loss, and take-profit exit reasons on fills and closed trades
- vectorized/event-driven parity, cost, CLI, validation, and persistence coverage

### Deferred Follow-ups

- short protective exits
- trailing stops
- richer order types and intrabar path simulation

---

## M6: Durable Persistence Foundation

Status: Implemented.

Ralph source: `backtester-durable-async-runs`.

### Goal

Persist immutable requests, lifecycle state, successful results, fills, and
closed trades through the existing database accessor stack.

### Implemented Scope

- versioned immutable request JSON and normalized lifecycle timestamps/status
- versioned metrics and diagnostics JSON
- normalized ordered fill and closed-trade tables with cascade deletion
- primitive create/get/list/delete, conditional update, and transactional
  completion operations in `database-accessor-api`
- synchronous and asynchronous shared-client methods
- synchronous CLI `--persist-result` using the same terminal result schema
- JSON request filters for symbol, timeframe, strategy, and engine

### Test Coverage

- mapping and schema-version tests
- filter and deterministic ordering tests
- compare-and-set race coverage
- atomic completion and rollback tests
- execution-log and cascade-deletion tests
- synchronous/asynchronous shared-client contract tests

### Acceptance Criteria

- accepted queued work is durable
- successful completion exposes all artifacts atomically
- failed runs contain no partial result artifacts
- persisted CLI and worker results share one schema

---

## M7: Durable Asynchronous API and Worker

Status: Implemented.

Ralph source: `backtester-durable-async-runs`.

### Goal

Expose a non-blocking lifecycle API and execute accepted work outside the API
process.

### Implemented Scope

- `POST /backtests` returning `202 Accepted`, `run_id`, and `Location`
- lifecycle, filtered history, fills, trades, and terminal deletion endpoints
- deterministic pre-persistence request validation
- separate API and singleton worker processes from the same image
- FIFO queue selection with atomic queued-to-running claiming
- spawned child-process execution from the immutable request
- parent-owned success/failure persistence and sanitized public errors
- startup reconciliation of interrupted running records
- configurable one-second worker polling default
- deployed success/failure smoke workflow

### Out of Scope

- cancellation, leases, heartbeats, retries, or execution timeouts
- multiple deployed workers or concurrent runs within one worker
- pagination, idempotency keys, or push completion notifications
- multi-tenant authentication

### Test Coverage

- submission, lifecycle response, filters, logs, and deletion route tests
- FIFO, claim-race, reconciliation, child isolation, and persistence-failure tests
- API/worker entrypoint and configuration tests
- deployed success/failure smoke-runner coverage

### Acceptance Criteria

- accepted work survives API restart
- child execution failures become terminal records without stopping future queue
  progress
- completion artifacts and succeeded state are transactionally visible together
- API and worker run as separate long-lived processes

### Deferred Follow-ups

- research and parameter-sweep UX over the durable API
- operational features listed in the out-of-scope section

---

## M8: Research Ergonomics

Status: Not implemented.

Ralph source: future PRD candidate for sweeps and research workflow
improvements.

Current gap: no `app/experiment_runner.py` or equivalent sweep use case exists,
the CLI still exposes only the single-run workflow, and the repository does not
yet include custom-strategy documentation, sweep output artifacts, or a second
example strategy.

### Goal

Improve day-to-day usability for strategy research.

### In Scope

- introduce `app/experiment_runner.py` or an equivalent focused sweep use case
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

## M8A: Bar-Mode Short Support

Status: Implemented.

Ralph source: `backtester-short-trades`.

Delivered capabilities:

- `ExecutionConfig.allowed_directions` explicitly supports `long_only`,
  `short_only`, and `long_and_short`.
- Signed targets, sizing, fills, portfolio quantities, reductions, covers, and
  direction flips are supported by both bar engines.
- The direction-neutral SMA crossover strategy maps its signals according to
  Allowed Directions and is exposed consistently through the CLI.
- Long and short protective exits share deterministic gap-through and ambiguous
  intrabar behavior.
- Closed trades persist explicit direction and planned protective prices;
  metrics report long/short counts, win rates, and realized PnL.
- Engine parity and API/CLI coverage exercise all three modes; end-to-end
  persistence coverage exercises short-trade artifacts.

### Goal

Support deterministic single-symbol bar-mode short trades in both vectorized and
event-driven engines while retaining explicit direction constraints.

### In Scope

- signed target quantity semantics:
  - positive target = long exposure
  - zero target = flat
  - negative target = short exposure when Allowed Directions permits it
- direction-neutral declarative strategy semantics interpreted according to the
  run's Allowed Directions
- sizing transforms that preserve target sign while applying fixed absolute size
- validation that rejects targets outside the configured Allowed Directions
- vectorized fill generation for long opens/closes, short opens/covers, and
  direct flips through flat accounting
- event-driven sequential runtime parity for the same signed-target semantics
- average-cost trade accounting for short round trips:
  - short entry on SELL
  - cover on BUY
  - realized PnL as entry price minus exit price, net of fees
- long and short stop-loss/take-profit protective exits:
  - long stop below entry and target above entry
  - short stop above entry and target below entry
  - deterministic ambiguous-bar handling through the existing
    `intrabar_exit_policy`
- persistence/API schemas with explicit closed-trade direction so consumers do
  not infer trade direction from fill sequence

### Out of Scope

- partial fills
- limit/stop order request objects separate from protective exits
- latency, spread/liquidity, queue-position, or broker margin modeling
- multi-symbol exposure netting
- tick support

### Deliverables

- all three Allowed Directions modes accepted for supported single-symbol
  bar-mode requests
- one reproducible direction-neutral strategy example
- vectorized/event-driven parity for long-only, short-only, and flip scenarios
- closed trades and metrics include short realized PnL correctly

### Executable Path

- run a short-capable strategy in vectorized and event-driven bar mode with
  `allowed_directions=long_and_short` and receive matching fills, trades, equity
  curve, metrics, and diagnostics.

### Test Coverage

- request-validation tests for all Allowed Directions modes
- unit tests for signed fixed sizing and direction validation
- fill-generation tests for open short, cover short, long-to-short flip,
  short-to-long flip, invalid-open gap policies, fees, and slippage
- trade-accounting tests for short round trips, partial covers if supported by
  target deltas, and direct flips producing closed trades
- protective-exit tests for short stop-loss/take-profit, gap-through fills, and
  ambiguous OHLC bars
- parity tests covering long-only regression, short-only, flip, costs, gap
  policy, no-lookahead, and bracket exits
- persistence/API tests for explicit closed-trade direction

### Acceptance Criteria

- `long_only`, `short_only`, and `long_and_short` constrain targets explicitly.
- Negative targets are supported only when the configured Allowed Directions
  permits short trades in the single-symbol bar-mode slice.
- Vectorized and event-driven engines produce matching public results for the
  agreed short-support parity matrix.
- Short protective exits are deterministic and documented in backtester context.

### Deferred Follow-ups

- richer order realism in M9
- margin, borrow cost, locate availability, and broker-specific short-sale rules

---

## M9: Richer Event-Driven Bar Execution

Status: Not implemented.

Ralph source: future PRD candidate for richer order realism.

Current gap: the current API and both engines still reject `allow_partial_fills`,
and there is no richer order request, partial-fill, latency, spread/liquidity,
queue-position, or optional realism mode. M8A established short support against
the existing next-open bar execution contract without introducing richer order
simulation.

### Goal

Increase event-driven execution realism on bar data beyond the M3 baseline cost model without breaking baseline parity mode.

### In Scope

- optional partial fills
- richer order request fields
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

Status: Not implemented.

Ralph source: future PRD candidate for tick support.

Current gap: tick enums and view types exist as forward-compatible contracts, but
`data_granularity=tick` is rejected before vectorized execution and no vectorized
tick replay path exists.

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

Status: Not implemented.

Ralph source: future PRD candidate for tick support.

Current gap: tick event shapes exist as forward-compatible contracts, but
`data_granularity=tick` is rejected before event-driven execution and no
sequential tick loop exists.

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
