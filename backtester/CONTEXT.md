# Backtester Context

Owns historical simulation, the public backtest API, and durable lifecycle policy.
For run/batch commands, queue invariants, versions, or replay format, read
[shared backtest contracts](../docs/contracts/backtests.md).

## Entry Points and Boundaries

- `src/app/backtest_runner.py` is the common orchestration for synchronous CLI
  and worker child execution. API submission validates and queues without loading
  Candles or running an engine.
- `src/app/backtest_runs.py`, `backtest_batches.py`, and `sweeps.py` own run policy,
  batch acceptance/commands, and stateless sweep expansion respectively.
- Run submission and batch acceptance take the optional top-level experiment
  name separately from execution requests/accepted definitions. Public schemas
  validate naming at creation; preview stays name-free. See
  [experiment names](../docs/contracts/backtests.md#experiment-names).
- Name-only commands use run/batch policy services and return identity plus the
  authoritative name. Renames accept every lifecycle state and reject members.
- `src/app/backtest_worker.py` owns claim/settlement orchestration;
  `backtest_child.py` supervises execution. Only the worker parent persists child
  results. `backtest_queue.py` projects advisory availability from storage and
  heartbeat primitives.
- `src/domain/types.py`, `enums.py`, and `events.py` own shared runtime concepts.
  `src/adapters/` maps external APIs and persistence into these contracts.
- Strategy authoring or parameter changes: read [STRATEGIES.md](STRATEGIES.md).
- Replay changes: start at `src/app/equity_replay.py` and the shared fingerprint
  contract. Persist descriptors and Fills, reconstruct curves on read.

## Simulation Vocabulary

- **Trade Direction:** `long` or `short`.
- **Allowed Directions:** `long_only`, `short_only`, or default `long_and_short`.
  `ExecutionConfig.allowed_directions` is the sole direction constraint; validate
  resulting targets, not fill side, and reject disallowed targets rather than
  clamping them. CLI exposes `--allowed-directions`.
- **Signed Target Quantity / Signed Portfolio Quantity:** desired / actual open
  quantity; positive is long, negative short, zero flat.
- **Strategy Signal:** directional intent. Zero holds the target. Direction-neutral
  SMA signals map bullish/bearish to long/short in `long_and_short`, to long/flat
  in `long_only`, and flat/short in `short_only`. An already-flat exit emits nothing.
- **Flat Target:** an explicit exit to cash, distinct from a zero hold signal.
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

## Engine Invariants

Supported execution is single-symbol bar data, close-time decisions, next-open
fills, and average-cost accounting. Tick simulation, multi-symbol execution, and
partial fills are rejected by the API and both engines. Event-driven mode accepts
declarative bar strategies; placeholder domain types do not establish support for
callback strategies or richer order simulation.

- `src/engines/vectorized.py` evaluates feature arrays, condition/signal masks,
  targets, fills, and portfolio arrays. Trim feature-incomplete rows before
  decisions; preserve the array-based runtime instead of per-bar interpretation.
- `src/engines/event_driven.py` bootstraps indicators from bars before `start_ms`,
  then executes sequentially over `[start_ms, end_ms)`. Bootstrap emits no trading
  artifacts. Indicator strategies require complete pre-start warmup; strategies
  without indicators may begin at the first in-window bar. Invalid features after
  bootstrap fail execution instead of silently skipping bars.
- Each tradable bar executes prior pending deltas at open, updates features and
  evaluates the completed bar, queues future deltas, then marks actual positions
  at close. The final decision expires without a next in-window open. Keep this
  runtime independent of vectorized fill/cumulative portfolio helpers.
- Invalid opens follow `gap_policy`: `skip` defers, `expire` drops, `error` raises.
  Deferred deltas net before execution. Fill timestamps identify the executing bar;
  sizing/risk apply before execution, with desired targets distinct from positions.
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
