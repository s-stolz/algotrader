# Ingestion Service Context

Consumes broker M1 Redis Candles, backfills missing history, and writes expanded
Candles through database-accessor-api. Shared payloads are in
[root context](../CONTEXT.md).

## History and Closed Candles

- `main.py` / `IngestionService` owns startup watermarks, tail IDs, stream-start
  order, chunking, backfill, reconnect recovery, writes, and shutdown.
- `app/stream_consumer.py` withholds the latest open Candle. It emits the previous
  Candle only when a newer timestamp arrives; this protects closed-candle storage.
- Resolve the configured lookback or UTC start date once per service instance.
  Empty Markets fetch from that inclusive boundary; populated Markets resume
  after their latest Candle, bounded by that boundary. Startup and reconnect use
  the same rule. Changing the boundary neither deletes history nor fills older
  history before an existing latest Candle.
- `app/broker_client.py` adapts historical trendbars and stream control;
  `app/db_client.py` wraps the shared accessor client. Keep broker and storage
  query parameter conventions at these boundaries.

History configuration is described in [config context](../config/CONTEXT.md).
For parsing changes, also inspect indicator-api and webserver consumers; storage
write changes reach [accessor context](../database-accessor-api/CONTEXT.md).

## Verification

Use `make test ingestion-service`. Cover startup/recovery boundaries, closed-candle
emission, and batching with controlled broker/Redis doubles.
