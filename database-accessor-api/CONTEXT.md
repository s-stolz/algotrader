# Database Accessor API Context

FastAPI interface for Markets and Candles stored in TimescaleDB.

## Owned Interfaces

- Market read/write shape and Market identity fields.
- Candle read/write HTTP routes and query parameters.
- Timeframe query semantics for raw M1 reads, continuous aggregates, and fallback
  bucketing.
- Timescale timestamp conversion between transport milliseconds and
  `timestamp_utc`.

## Key Modules

- `main.py`: FastAPI routes for health, markets, candle reads, candle writes,
  latest candle, and deletes.
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
