# Database Accessor API Context

FastAPI persistence interface for Markets, Candles, and durable backtest runs
stored in TimescaleDB.

## Owned Interfaces

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
  remains readable without assigning a current version. Both use Allowed Directions.
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
- Run deletion removes the parent row and relies on database foreign-key cascades
  for fills and trades; terminal-state policy remains in the backtester.
- Backtester code owns lifecycle transitions, queue selection, and scheduling.
  This service accepts caller-owned run identity and state as persistence data.
- The execution slot is a single database row. Accessor claim checks the oldest
  queued standalone run and free slot in one transaction; settlement requires the matching
  owner token and commits terminal state, artifacts, and slot release together.
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
