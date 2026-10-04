# Ingestion Service

A Python service that consumes market data from Redis streams and persists it to TimescaleDB via the database-accessor-api.

## Features

- **Automatic Backfill**: Downloads initial history and catches up after the latest stored candle through broker-service
- **Redis Stream Consumer**: Consumes candle data using XREAD
- **Dynamic Symbol Loading**: Fetches active symbols from the markets table
- **Batch Processing**: Efficiently batches candles before writing to database
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals

## Data Contracts

For timestamp and payload fields, read [root context](../CONTEXT.md).
For closed-candle and recovery behavior, read [service context](CONTEXT.md).

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
# From the repository root
make up-build
```

## Architecture

```
Redis Streams → Ingestion Service → Database Accessor API → TimescaleDB
```

The service:
1. Fetches active symbols from database-accessor-api
2. Downloads initial history or catches up through broker-service
3. Continuously consumes new candle data from Redis
4. Transforms and batches data before writing via HTTP POST

## Historical download range

The tracked default downloads the last **90 days** for markets without stored
candles. For machine-specific values, create `config/topology.local.yaml`:

```yaml
services:
  ingestion_service:
    history:
      lookback_days: 30
      start_date: null
```

For a fixed start, use `lookback_days: null` and `start_date: "2024-01-01"`.
Exactly one option must be active. Dates start at midnight UTC; days are calendar
days, including weekends. The boundary is resolved once when the service starts.

Run `make config` and recreate ingestion-service to apply the generated values
(`INGESTION_HISTORY_LOOKBACK_DAYS` / `INGESTION_HISTORY_START_DATE`). Direct process
launches must load the generated environment as usual.

Existing markets resume after the latest stored candle, never earlier than the
configured boundary. Reconnect recovery uses the same rule. Reducing the range
does not delete stored candles; increasing it does not fetch older history for
already populated markets. Older-history backfill remains a separate operation.
