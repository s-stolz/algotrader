# Ingestion Service

A Python service that consumes market data from Redis streams and persists it to TimescaleDB via the database-accessor-api.

## Features

- **Automatic Backfill**: On startup, detects missing data gaps and backfills from Redis streams
- **Redis Stream Consumer**: Consumes candle data using XREAD
- **Dynamic Symbol Loading**: Fetches active symbols from the markets table
- **Batch Processing**: Efficiently batches candles before writing to database
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals

## Timestamp Contract

- Consumes Redis candle events in compact format with one-character keys: `o`, `h`, `l`, `c`, `v`, `t`.
- `t` is UTC epoch milliseconds.
- Persists candles via database-accessor-api using `timestamp_ms` (UTC epoch milliseconds).
- No local timezone conversion is performed during ingestion.

## Configuration

Configuration is centralized at the repository root.

```bash
cd ..
cp config/.env.secrets.example config/.env.secrets.local
python scripts/generate_env.py
cd ingestion-service
```

Key settings:
- `REDIS_URL`: Redis connection string
- `DATABASE_ACCESSOR_HOST` / `DATABASE_ACCESSOR_PORT`: Database accessor API endpoint
- `ACCOUNT_ID`: cTrader account ID for Redis stream keys

## Running

### Local Development
```bash
python -m pip install -r requirements.txt
python main.py
```

### Docker
```bash
docker build -t ingestion-service .
docker run --env-file .env ingestion-service
```

## Architecture

```
Redis Streams → Ingestion Service → Database Accessor API → TimescaleDB
```

The service:
1. Fetches active symbols from database-accessor-api
2. Checks for data gaps and backfills from Redis streams
3. Continuously consumes new candle data from Redis
4. Transforms and batches data before writing via HTTP POST
