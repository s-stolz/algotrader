# Database Accessor API Context

FastAPI persistence interface for Markets, Candles, and durable backtest runs
stored in TimescaleDB.

## Owned Interfaces

- Primitive `GET /backtest-execution/queue-state` and
  `POST /backtest-execution/heartbeat` expose database-clock worker telemetry,
  durable slot identity, and ordered standalone/batch turns to the backtester.
  The accessor does not decide availability or persist advisory positions.

- Market read/write shape and Market identity fields.
- Candle read/write HTTP routes and query parameters.
- Timeframe query semantics for raw M1 reads, continuous aggregates, and fallback
  bucketing.
- Timescale timestamp conversion between transport milliseconds and
  `timestamp_utc`.
- Primitive durable backtest run create/get/list/delete, fill/trade reads,
  conditional update, and transactional successful-completion storage operations.

## Key Modules

- `main.py`: FastAPI routes for health, markets, candles, and backtest run
  persistence.
- `app/crud.py`: SQLAlchemy and SQL query helpers, candle query planning,
  continuous aggregate fallback, bucketing, and timestamp conversion.
- `app/market_cache.py`: in-process market cache and symbol resolution.
- `app/timeframes.py`: API Timeframe enum and minutes conversion.
- `app/schemas.py`: Pydantic request and response models.
- `app/models.py`: SQLAlchemy table definitions.
- `app/database.py`: async database session setup.

## Contracts

- Market rows include `symbol_id`, `symbol`, `exchange`, `market_type`, `min_move`,
  and `timezone`.
- Candle transport and Timescale storage follow root `CONTEXT.md`.
- Query params use `start_ms`, `end_ms`, `limit`, `timeframe`, and optional
  `exchange`.
- M1 reads use the raw `candles` table. Higher timeframe reads may use Timescale
  continuous aggregates or direct `time_bucket` fallback.
- Backtest request attributes live only in versioned `request` JSON. New schema
  version 3 adds exact Strategy Version and resolved parameters; version 2
  remains readable without assigning a current version. The accessor omits
  `strategy_version` from serialized version-2 responses when the stored request
  has no version; sending a synthesized `null` would break strict historical
  readers. Both use Allowed Directions.
  Lifecycle status and timestamps are normalized columns; result metrics,
  diagnostics, and Equity Replay descriptor are nullable JSON documents.
- New request JSON uses schema version 3. The accessor preserves historical
  version 2 request JSON without backfill. New completed results use schema
  version 3; stored result versions 1 and 2 remain readable for inspection.
  Current closed trades include nullable planned protective exit prices and
  required closed-trade direction.
- Forward-only upgrades preserve earlier terminal results, Fills, and Closed
  Trades; older successes without replay metadata report its unavailable reason.
- Stored backtest closed-trade `trade_direction` is required and limited to
  `long` or `short`.
- Run listing filters status and submission dates through lifecycle columns and
  symbol, timeframe, strategy, and engine through immutable request JSON. Symbol
  matching uses collection membership. Results use `submitted_at DESC`, then
  `run_id ASC`, with no persistence-layer limit or queue-selection policy.
- Primitive `/backtest-batches` create/list/detail/member/event routes store one
  accepted batch with all members and an initial revision-zero event in one
  transaction. Same-submission-ID retries compare the normalized accepted
  definition and return the existing batch; a different definition conflicts.
  Member reads are ordinal ordered. Run reads may filter standalone or batch
  membership without changing unfiltered results.
- The standalone create route rejects batch identity, direct member deletion
  conflicts, and a standalone queued-to-running compare-and-set excludes batch
  members. SQL constraints and triggers protect immutable request/membership,
  unique ordinals, and accepted batch membership after transaction commit.
- Backtest fills and closed trades are normalized child rows with caller-supplied
  sequence values and cascade deletion.
- Backtest closed trades carry explicit trade direction plus nullable
  `stop_loss_price` and `take_profit_price` values for planned protective exit
  levels.
- Fill and trade reads are ordered by their per-run sequence values. Missing parent
  runs return not found, while existing runs with no child rows return empty lists.
- Run deletion locks the execution slot and run, rechecks terminal standalone
  state and membership, and removes the parent and its artifacts atomically.
  Whole-batch deletion locks the slot, batch, and members, rechecks settled
  state, and deletes the parent; database cascades remove members, results,
  replay descriptors, Fills, Closed Trades, events, and command receipts.
  Missing resources return 404, while ineligible state or membership returns 409.
- Backtester code owns lifecycle transitions, queue selection, and scheduling.
  This service accepts caller-owned run identity and state as persistence data.
- The execution slot is a single database row. Accessor claim locks that row,
  verifies the earliest durable turn, batch eligibility, and lowest queued
  member ordinal, and atomically claims one run. Settlement requires the matching
  owner token and commits terminal state, artifacts, batch reconciliation/events,
  the next turn, and slot release together. `POST /backtests/{run_id}/cancel`
  serializes on the same slot: queued runs become cancelled without occupying it, while running
  runs become cancelling and keep it until a fenced cancelled settlement.
  The acceptance time, source, and reason persist on the run. A member
  cancellation advances the batch revision and records a same-state command
  event; final-member settlement changes the batch control state separately.
  Startup reconciliation settles cancelling work only after the previous process
  tree is confirmed gone and the slot is cleared by the operator. Batch creation
  and standalone submission serialize turn insertion through the same slot row;
  existing queued work was
  seeded in submission-time/identity order by V011.
  Automatic event rows record the locked batch's prior status and new status;
  pause/resume command rows also retain the unique client command identity.
  Control transactions take the execution-slot lock before the batch lock, remove
  turns on Pause, and append eligible turns at the tail on Resume or settlement.
  The backtester passes legal/effective transition policy; the accessor applies
  that plan against the locked current state.
  A command receipt also preserves no-op command identity without incrementing
  revision or appending an event. Accepted revision-zero and pre-V012 events have
  a null prior status.
  Cancel Batch uses the same slot and batch locks. It removes the batch turn,
  cancels queued members, marks active work cancelling, and records acceptance
  time/provenance and one revisioned command event in a single transaction.
  An idle batch becomes cancelled in that transaction. An active batch remains
  cancelling with its slot held until verified child exit and fenced settlement
  or startup reconciliation. Prior terminal rows and artifacts are untouched;
  command receipts make same-ID retries stable across later settlement.
  Successful settlement requires a validated Equity Replay descriptor; failed
  settlement rejects replay metadata and other result artifacts.
  Faults remain separate from durable run history. Reconciliation is conditional
  on a free, unfaulted slot and preserves queued work.
- With the slot row installed, legacy tokenless conditional updates and completion
  return `updated=false` for every expected status, including after manual slot
  clear; only owner-token settlement may commit a worker outcome or its artifacts.
- Before slot installation, conditional updates compare the stored status with
  `expected_status` in the update statement and return `updated=false` on a stale
  expected status.

## Change Triggers

- `crud.py` owns valuable storage behavior but combines raw reads, aggregate reads,
  fallback bucketing, sorting, limit reversal, and timestamp conversion.
- Market resolution and cache refresh behavior lives in route code plus
  `market_cache.py`.
- If Timeframe support changes, update `libs/db_accessor_client`,
  `frontend/src/utils/timeframes.ts`, `broker-service`, and `timescaledb-init`
  context as needed.

## Verification

- There is currently little source-level coverage in this area. Prefer adding
  tests around candle query semantics before changing `crud.py`.
- Run affected shared client, ingestion, indicator, backtester, or frontend tests
  when route contracts change.

- Successful completion requires a validated Equity Replay descriptor in the same
  transaction as metrics, diagnostics, Fills, and Closed Trades. The nullable
  column preserves pre-upgrade successful runs without backfill.
