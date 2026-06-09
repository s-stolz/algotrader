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
- Primitive durable backtest run create/get/list, conditional update, and
  transactional successful-completion storage operations.

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
- Backtest request attributes live only in versioned `request` JSON. Lifecycle
  status and timestamps are normalized columns; result metrics and diagnostics
  are nullable versioned JSON documents.
- Run listing filters status and submission dates through lifecycle columns and
  symbol, timeframe, strategy, and engine through immutable request JSON. Symbol
  matching uses collection membership. Results use `submitted_at DESC`, then
  `run_id ASC`, with no persistence-layer limit or queue-selection policy.
- Backtest fills and closed trades are normalized child rows with caller-supplied
  sequence values and cascade deletion.
- Backtester code owns lifecycle transitions, queue selection, and scheduling.
  This service accepts caller-owned run identity and state as persistence data.
- Conditional updates compare the stored status with `expected_status` in the
  update statement. Successful completion updates the parent run and inserts all
  fills and trades in one transaction, returning `updated=false` on a stale
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
