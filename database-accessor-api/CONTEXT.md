# Database Accessor API Context

FastAPI persistence primitives for Markets, Candles, and backtests in TimescaleDB.
Transport contracts live in [root context](../CONTEXT.md); durable Backtest/Run
semantics live in [backtest contracts](../docs/contracts/backtests.md).

## Candle Queries

- `app/crud.py` owns raw M1 reads, continuous aggregate selection, direct bucketing
  fallback, sorting, limit reversal, and transport/storage timestamp conversion.
  Check these together when changing query behavior.
- `main.py` and `app/market_cache.py` share Market resolution and cache refresh.
- `app/timeframes.py` defines API Timeframes. Coordinate changes with the shared
  client, broker, frontend options, and Timescale aggregates through the
  [contract map](../docs/agent/CONTRACT-CHANGES.md).

## Backtest Storage

`app/backtest_execution.py` owns slot-serialized execution operations;
`app/crud.py` also handles Backtest/Run creation and history. `app/models.py` and
`app/schemas.py` define storage and transport shapes. Backtester supplies
lifecycle policy; the accessor applies it against locked current state.

- `BacktestExecutionPayload` validates persisted execution settings separately
  from the public backtester schema. Keep optional controls coordinated across
  both boundaries: order mode, quote convention, spread, intrabar policy, position
  limits, daily schedules, and entry limits must survive storage HTTP
  round trips, while disabled controls stay omitted for legacy representations.
- Lock the execution slot before Backtest/Run rows for control transactions.
  Submission turn insertion and queue snapshots use that same lock. Queue reads
  hold it through the read transaction so active ownership and waiting turns
  cannot come from different lifecycle states.
- Claim verifies the head turn, Backtest eligibility, and lowest queued member.
  Claims require a worker identity and seed the matching heartbeat atomically; heartbeat
  writes take the slot lock and fence delayed ownership changes.
  Settlement requires the owner token and commits artifacts, outcome, Backtest
  reconciliation/events, next turn, and slot release together.
- Cancellation, pause/resume, deletion, and startup reconciliation must preserve
  those transaction boundaries. No-op command receipts retain identity without
  adding a revision/event; retries return the original result after later changes.
- Backtest acceptance persists a normalized top-level name separately from JSON
  snapshots. Runs have required parent IDs and ordinals and no independent names.
  Apply [naming rules](../docs/contracts/backtests.md#experiment-names) at storage.
- Name-only updates lock the parent row and change only its name, without changing
  execution-slot ownership, revisions, events, or queue turns.
- Membership guards reject late insertion, replacement, and direct Run deletion.
  Whole-Backtest deletion cascades through all artifacts after settlement.
- Filter request attributes from immutable JSON, including collection membership
  for symbol matching. Keep lifecycle fields normalized rather than copying
  request attributes into columns.
- Successful worker settlement validates and stores the replay descriptor with
  metrics, diagnostics, Fills, and Closed Trades. Failed settlement rejects result
  artifacts. Worker lifecycle writes use only the owner-token-fenced execution
  endpoints; the tokenless update and completion endpoints have been retired.
- Fill/trade reads use sequence order: missing parent is 404, existing parent with
  no children is an empty collection. Deletion is 204, missing is 404, ineligible
  state/membership is 409; recheck eligibility inside the locked transaction.

For schema changes, read [Timescale context](../timescaledb-init/CONTEXT.md).

## Verification

Use `make test database-accessor-api`. Candle limit behavior is covered by
`tests/test_crud_m1_limit.py`; backtest mapping/routes by `tests/test_backtests_api.py`.
Transaction, cancellation, claim/settlement, and deletion races require the opt-in
`tests/test_backtest_*postgres.py` suites; [commands](../docs/agent/COMMANDS.md#live-storage-verification)
explains setup. Include affected shared-client and public backtester tests when
changing persistence interfaces.

# Database Accessor Context

The accessor owns Market resolution and persistence transactions. Ordinary live
Candle inserts in `app/crud.py` retain existing rows; authoritative closed M1
writes in `app/historical_candles.py` replace OHLCV using the same uniqueness key.
Read [Candle persistence](../docs/contracts/candles.md) before changing either
write path. `tests/test_historical_candles_postgres.py` verifies real Timescale
behavior through the API, including compressed history and concurrent writes.

## Pending recovery

**Pending recovery** means unfinished history retrieval for a logical
Market/account/M1 source. It is not general historical completeness. For source
identity, conditional progress/completion and protected startup obligations, read
the [recovery contract](../docs/contracts/recovery.md).

**Live write guard:** the durable pre-batch confirmed boundary for an unconfirmed
live Candle write. Partial commits and lost receipts cannot hide it behind a
newer latest Candle; normal successful live writes retire it without scheduling
history. See the [guard contract](../docs/contracts/recovery.md#durable-live-write-guards).
