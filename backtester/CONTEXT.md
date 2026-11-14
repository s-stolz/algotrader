# Backtester Context

Owns historical simulation, the public backtest API, and durable lifecycle policy.
For Backtest/Run commands, queue invariants, versions, or replay format, read
[shared backtest contracts](../docs/contracts/backtests.md).

## Entry Points and Boundaries

- `src/app/execution_log.py` owns eligibility for bounded saved execution-log pages; the accessor performs pagination and optional unexecuted-order projection. See the shared contract.

- `src/app/backtest_runner.py` orchestrates simulations for worker child execution
  and callers supplying historical bars. API submission validates and queues
  without loading Candles or running an engine.
- `src/app/backtest_runs.py`, `backtests.py`, and `backtest_definitions.py` own
  Run reads/cancellation, Backtest acceptance/commands, and stateless expansion.
- `backtest_definitions.py` expands optional schedule alternatives as whole UTC
  triples after direction choices. API selection lists become individual existing
  execution schedules before worker execution; engine timing semantics are unchanged.
- Backtest acceptance takes the optional name separately from execution requests
  and accepted definitions. Preview stays name-free. Names belong to Backtests;
  all Runs are accepted and deleted with their parent. See
  [shared contracts](../docs/contracts/backtests.md).
- `src/app/backtest_worker.py` owns claim/settlement orchestration;
  `backtest_child.py` supervises execution. Claims carry the same process identity
  as periodic heartbeats so storage can establish freshness atomically.
  Only the worker parent persists child
  results. Stage observations live in `domain/progress.py`; the execution child
  writes shared stage and candle counters and the parent publishes advisory progress
  snapshots. Event-driven loops report coarse counts through `CandleProgress`;
  the child performs no network publication.
  See [run progress](../docs/contracts/backtests.md#run-stage-progress).
  `backtest_queue.py` projects advisory availability from storage and
  heartbeat primitives.
- `src/domain/types.py`, `enums.py`, and `events.py` own shared runtime concepts.
  `src/adapters/` maps external APIs and persistence into these contracts.
- Strategy authoring or parameter changes: read [STRATEGIES.md](STRATEGIES.md).
  Local modules belong in the ignored `src/strategies/custom/` package; their
  supporting artifacts belong in ignored `private/`. Docker build contexts exclude
  both; local API/worker Compose mounts supply them at runtime. See the
  [private workspace contract](STRATEGIES.md#private-strategy-workspace).
- `src/reporting/metrics.py` records ending equity from the final portfolio
  snapshot in saved metrics; table inspection does not need Equity Replay.
  It also owns [saved profit factor](../docs/contracts/backtests.md#saved-profit-factor)
  for every engine path; child handoff preserves the explicit JSON union.
- Replay changes: start at `src/app/equity_replay.py` and the shared fingerprint
  contract. Persist descriptors and Fills, reconstruct curves on read.

## Simulation Vocabulary

- **Trade Direction:** `long` or `short`.
- **Allowed Directions:** `long_only`, `short_only`, or default `long_and_short`.
  `ExecutionConfig.allowed_directions` is the sole direction constraint; validate
  resulting targets, not fill side, and reject disallowed targets rather than
  clamping them.
- **Signed Target Quantity / Signed Portfolio Quantity:** desired / actual open
  quantity; positive is long, negative short, zero flat.
- **Strategy Signal:** directional intent. Zero holds the target. Direction-neutral
  SMA signals map bullish/bearish to long/short in `long_and_short`, to long/flat
  in `long_only`, and flat/short in `short_only`. An already-flat exit emits nothing.
- **Flat Target:** an explicit exit to cash, distinct from a zero hold signal.
  Declarative `flat_conditions` emit `StrategySignal.FLAT` independently of
  indicator availability and directional filters, taking priority over long/short
  signals. Both engines map this action to a zero target in every direction mode;
  normal target transforms, next-open fills, and gap policies still apply.
- **Position Reduction:** reduce without reversing; the requested delta still
  fills completely or not at all.
- **Short Cover:** a buy that reduces/closes a short position.
- **Direction Flip:** cross through flat. A `+1` to `-1` change is one sell Fill
  of quantity 2 but separate round-trip trade accounting. Allocate fees pro rata
  between the closing and opening quantities (**Flip Fee Allocation**).
- **Short Trade / Closed Trade Direction:** the explicit direction of a completed
  round trip. Fills retain execution side because a flip can close and open trades.
- **Closed Trade Quantity:** positive absolute size. Long PnL uses exit minus
  entry; short PnL uses entry minus exit; fees reduce both.
- **Short Protective Exit:** stop above entry, target below entry.
- **Protective Exit Reset:** a protective exit resets the desired target to flat;
  re-entry needs a later signal or target change.
- **Direction Breakdown Metrics:** long/short counts, win rates, realized PnL.
  Empty-direction win rates are zero; total trade count includes both directions.

- **Order Command:** a close-time submission, update, cancellation, or position
  protection update, effective from the following minute.
- **Execution Candle:** the M1 Candle used to match pending orders; distinct from
  the strategy Candle used to calculate a decision.
- **Partial Protective Close:** a fully executed reduce-only order that closes
  part of the net position; distinct from a liquidity-based partial order fill.

Tick-based order protection uses `BacktestRequest.market_min_move`, resolved per
Market during acceptance and preserved in the immutable request snapshot. See
[market price increments](../docs/contracts/backtests.md#market-price-increments).

## Engine Invariants

Supported execution is single-symbol bar data, close-time decisions, and
average-cost accounting. Default target mode uses next-open fills. Explicit order
mode uses persistent limit orders with M1 execution; see [order contracts](ORDERS.md). Tick simulation, multi-symbol execution, and
partial fills are rejected by the API and both engines. Event-driven mode accepts
declarative bar strategies; placeholder domain types do not establish support for
arbitrary tick callbacks. `OrderStrategyModel` explicitly provides array and
completed-candle evaluators for order mode.

Additional indicator input Markets do not become executable Markets. The loader
discovers them from indicator specifications; caller-supplied runs provide their
source frames explicitly. See [strategy input contracts](STRATEGIES.md#indicator-inputs).

- `src/engines/vectorized.py` evaluates feature arrays, condition/signal masks,
  targets, fills, and portfolio arrays. Ordinary single-source indicators retain
  feature trimming. Multi-source/anchored indicators retain execution rows and
  expose causal availability instead. Preserve the array-based runtime instead
  of per-bar interpretation. Sized targets use `execution/target_arrays.py` to
  select decision, protective, depletion, and schedule events with array masks;
  only those bars enter the OHLC matcher. Fill deltas, notionals, and fees feed
  cumulative portfolio arrays, including quiet bars between events.
- `src/engines/event_driven.py` bootstraps indicators from bars before `start_ms`,
  then executes sequentially over `[start_ms, end_ms)`. Both engines use the same
  history loader for ordinary indicators: the initial time window is supplemented
  with older candles by count across gaps and closures. Warmup includes the first
  executable candle (an N-candle indicator needs N-1 predecessors). If stored
  history is exhausted before warmup is complete at `start_ms`, warmup continues
  through in-window candles until the first complete snapshot,
  matching vectorized initial feature trimming. Warmup emits no trading artifacts
  or equity points; the requested start remains unchanged. A window that never
  completes warmup fails with no executable bars. Strategies without indicators
  may begin at the first in-window bar. Ordinary indicator features invalid after
  warmup fail event-driven execution. Multi-source/anchored inputs
  instead suppress directional entry signals while preserving position management.
  Their bootstrap initializes calculations only; crossover decisions begin with
  in-window snapshots in both engines.
- Each tradable bar executes prior pending deltas at open, evaluates the completed
  bar's features, queues future deltas, then marks actual positions
  at close. The final decision expires without a next in-window open. Keep this
  runtime independent of vectorized fill/cumulative portfolio helpers.
- Invalid opens follow `gap_policy`: `skip` defers, `expire` drops, `error` raises.
  Deferred deltas net before execution. Fill timestamps identify the executing bar;
  sizing/risk apply before execution, with desired targets distinct from positions.
- Optional `ExecutionConfig.daily_schedule` boundaries constrain fills at the destination
  open in both engines. Entry windows are UTC and exclude the last-entry cutoff;
  positions retain their entry day's exit deadline through gaps. Overdue exits
  retry until a valid in-range open. Calendar actions do not depend on indicator
  availability. Runtime scheduling stays independent between engines; the domain
  schedule shares only boundary validation and UTC arithmetic. See
  [daily execution schedules](STRATEGIES.md#daily-execution-schedule).
- Optional `ExecutionConfig.max_entries_per_day` counts actual exposure-increasing
  fills per UTC day and per run, including same-bar stop-outs and reversals.
  Both independent runtimes enforce the limit before fills; exits remain eligible.
  See [daily entry limits](STRATEGIES.md#daily-entry-limit).
- Protective exits activate on the entry fill bar. Gap-through exits fill at open;
  intrabar touches fill at their level. Ambiguous stop/target bars follow
  `intrabar_exit_policy`, defaulting to stop-first. Preserve engine parity for
  prices, fees, and slippage.
- Trades retain `signal`, `stop_loss`, or `take_profit` exit reasons and planned
  protection levels. `signal_exit_count` counts exit Fills, not unfilled signals;
  protective diagnostics aggregate directions while metrics split them.

## Worker Constraints

Async execution requires Linux subreaping and readable `/proc`; use Compose on
other hosts. A supervisor adopts and reaps descendants, including detached
sessions, before reporting completion, and the worker reaps that supervisor.
Missing containment or uncertain exit retains the slot. Child output is compact
and excludes the equity curve. For upgrade, cleanup faults, or held slots, follow
[worker recovery](../docs/operations/backtest-worker-recovery.md) and
[ADR-0007](../docs/adr/0007-backtest-execution-slot-requires-verified-recovery.md).

API `/health` checks process readiness; `/backtests/queue/health` checks worker
availability and returns 503 for stale, absent, faulted, or unreadable state.

## Verification

Use `make test backtester`; direct test/module invocations need `PYTHONPATH=src`.
Test `long_and_short` as the default and both restricted modes as supported paths.
Engine changes need no-lookahead, warmup, gap, accounting, protective-exit, and
parity coverage, including guards against substituting one runtime for the other.
For deployed lifecycle checks use `make smoke-backtester`. Shared client/indicator
changes also need their affected consumer tests; see [commands](../docs/agent/COMMANDS.md).

Sized Runs use `domain/risk.py` for linear valuation and submission-time decisions.
The independent order matchers enforce reservations, fill affordability, and
intrabar depletion. `sized_targets_vectorized.py` consumes array-derived signals;
`sized_targets_event_driven.py` consumes sequential feature decisions. Legacy Runs
without sizing continue through their original target execution paths. The full
policy is owned by [sizing and margin](../docs/contracts/backtests.md#sizing-instrument-valuation-and-margin).

For progressive Equity Replay, `src/app/equity_stream.py` owns provisional
reconstruction and final verification. The API closes downstream Candle streams
on disconnect. See [streaming replay contracts](../docs/contracts/backtests.md#streaming-equity-replay).
