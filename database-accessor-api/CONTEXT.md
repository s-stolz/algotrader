# Database Accessor API Context

FastAPI persistence primitives for Markets, Candles, and backtests in TimescaleDB.
Transport contracts live in [root context](../CONTEXT.md); durable run/batch
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
`app/crud.py` also handles run/batch creation and history. `app/models.py` and
`app/schemas.py` define storage and transport shapes. Backtester supplies
lifecycle policy; the accessor applies it against locked current state.

- Lock the execution slot before batch/run rows for control transactions.
  Submission turn insertion and queue snapshots use that same lock. Queue reads
  hold it through the read transaction so active ownership and waiting turns
  cannot come from different lifecycle states.
- Claim verifies the head turn, batch eligibility, and lowest queued member.
  Settlement requires the owner token and commits artifacts, outcome, batch
  reconciliation/events, next turn, and slot release together.
- Cancellation, pause/resume, deletion, and startup reconciliation must preserve
  those transaction boundaries. No-op command receipts retain identity without
  adding a revision/event; retries return the original result after later changes.
- Run/batch creation persists a normalized top-level name separately from JSON
  snapshots. Members cannot carry a custom name; legacy name/label request
  metadata is rejected on new submissions. Apply
  [experiment-name rules](../docs/contracts/backtests.md#experiment-names) at the storage boundary.
- Name-only updates validate at the persistence boundary and update only `name`.
  Member guards run under the run row lock; these writes never acquire or change
  the execution slot, revisions, event history, or queue turns.
- Standalone create rejects batch identity. Membership guards reject late member
  insertion/replacement and direct member deletion while the batch exists.
- Preserve version-2 request JSON. When `strategy_version` was absent, omit it
  from serialized responses; synthesizing `null` breaks strict historical readers.
- Filter request attributes from immutable JSON, including collection membership
  for symbol matching. Keep lifecycle fields normalized rather than copying
  request attributes into columns.
- Successful worker settlement validates and stores the replay descriptor with
  metrics, diagnostics, Fills, and Closed Trades. Failed settlement rejects result
  artifacts. Tokenless legacy completion returns `updated=false` once the slot
  exists, even after manual slot clear.
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
