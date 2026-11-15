# Ingestion Service

A Python service that consumes market data from Redis streams and persists it to TimescaleDB via the database-accessor-api.

## Features

- **Durable Recovery**: Protects a saved boundary before live writes and retrieves broker history
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
Create the service environment with `make venv SERVICE=ingestion-service`.
A direct launch requires the generated shared and runtime-secret variables in
the process environment, with Redis, broker, and accessor addresses reachable
from the host. Generating files does not load them.

```bash
cd ingestion-service
.venv/bin/python main.py
```

Use Compose below to load the generated environment and service networking automatically.

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

## Market sources and history

Broker Markets bound to the configured account collect live M1 candles from their
creation boundary. Custom Markets use uploaded data and never start broker requests.
New Markets are discovered without restarting ingestion. Selecting Skip in the history
dialog does not disable live collection or recovery after interruptions.

Historical downloads are explicit requests from the market's Download historical data
menu. They extend older data without replacing existing candles. The legacy global
lookback configuration no longer schedules initial history for new broker Markets.

For durable pending recovery and protected startup, read the
[recovery contract](../docs/contracts/recovery.md).
