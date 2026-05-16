# Ingestion Service Context

Worker that keeps stored M1 candles current by consuming Redis candle streams and
backfilling missing data through broker-service.

## Owned Interfaces

- M1 Redis Candle ingestion from broker-service streams.
- Closed-candle emission rule for storage writes.
- Backfill and recovery calls to broker-service historical trendbars.
- Expanded Candle writes through database-accessor-api.

## Key Modules

- `main.py`: `IngestionService`, startup, per-symbol runtime state, backfill,
  recovery, consumer task management, and shutdown.
- `app/stream_consumer.py`: Redis XREAD consumer, compact candle parsing, and
  closed-candle emission.
- `app/broker_client.py`: broker-service historical trendbar and stream control
  adapter.
- `app/db_client.py`: wrapper around shared `db_accessor_client`.
- `app/config.py`: environment configuration.

## Contracts

- Consumes M1 Redis candle streams defined in root `CONTEXT.md`.
- Writes expanded candles through database-accessor-api.
- Ingestion currently targets M1 storage and uses broker stream backfill for gaps.

## Change Triggers

- `IngestionService` owns startup watermarks, stream tail IDs, broker stream start
  order, startup backfill, reconnect recovery, chunking, and writes.
- `StreamConsumer` deliberately withholds the latest open candle and emits only
  the previous candle after a newer timestamp arrives.
- When changing candle parsing or closed-candle rules, inspect `indicator-api`
  live parsing and `webserver` Redis parsing too.
- If storage write semantics change, inspect `database-accessor-api/CONTEXT.md`
  and root `CONTEXT.md`.

## Verification

- Ingestion tests: `make test ingestion-service`.
- Prefer tests that cover startup backfill, recovery backfill, closed-candle
  emission, and write batching without live Redis or broker calls.
