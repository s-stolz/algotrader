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
  Empty Markets fetch from that inclusive boundary; populated Markets include
  their latest Candle, bounded by that boundary. Startup and reconnect use
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

# Ingestion history context

**Closed M1 Candle:** a Candle whose UTC minute ended before the frozen history
request boundary. The current open minute is excluded from recovery.

**Completed empty history:** a successfully verified interval with no
broker-available Candles, including ordinary Market closures.

**Partial historical delivery:** an unsuccessful download even when some Candles
arrived; it cannot count as completed recovery.

**Recovery boundary:** inclusive beginning of broker history still to verify.

**Pending recovery:** durable unfinished work for a Market/account/M1 source.
Newer live rows and history-policy changes cannot erase it. It is not a general
completeness index or an inference from ordinary Market silence.

**Historical window:** a finite closed interval whose complete retrieval and
confirmed writes are required before advancing pending recovery.

For protected startup, triggers, concurrency/retry/shutdown obligations,
configuration, migration and real process acceptance, read the
[recovery contract](../docs/contracts/recovery.md). For authoritative correction,
compressed storage and partial-write replay, read
[Candle persistence](../docs/contracts/candles.md). Broker delivery completion is
owned by the [historical transport contract](../broker-service/HISTORY.md).

**Publication continuity:** per-message identity of uninterrupted live delivery.
A changed identity requires durable recovery protection before live persistence.

**Untrusted live data:** a Redis Candle with absent or invalid continuity. It can
be recovered historically, but cannot be admitted as an unprotected live write.

For mixed sessions, retained legacy rows and compatible consumer rollout, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).

**Dependency interruption:** an observed Redis read or database persistence failure
that requires recovery even when publication continuity is unchanged. A failed
live batch remains unconfirmed until its entire persistence callback succeeds.

**Live write guard:** the durable pre-batch confirmed boundary for an unconfirmed
live Candle write. Partial commits and lost receipts cannot hide it behind a
newer latest Candle; normal successful live writes retire it without scheduling
history. See the [guard contract](../docs/contracts/recovery.md#durable-live-write-guards).
