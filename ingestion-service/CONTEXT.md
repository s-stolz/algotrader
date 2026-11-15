# Ingestion Service Context

Consumes broker M1 Redis Candles, backfills missing history, and writes expanded
Candles through database-accessor-api. Shared payloads are in
[root context](../CONTEXT.md).

## History and Closed Candles

- `main.py` / `IngestionService` owns startup watermarks, tail IDs, stream-start
  order, chunking, backfill, reconnect recovery, writes, and shutdown.
- Health restoration or a changed broker instance renews desired subscriptions
  under durable recovery protection, even when no new Candle has arrived.
- `app/stream_consumer.py` withholds the latest open Candle. It emits the previous
  Candle only when a newer timestamp arrives; this protects closed-candle storage.
- Only Markets bound to the configured cTrader account/environment enter ingestion.
  Custom Markets never start broker subscriptions or recovery. Reconciliation discovers
  new and removed Markets without a restart; removal cancels and drains owned tasks.
- New broker Markets start at their server-owned `live_start_ms`, not the legacy
  global history lookback. Empty-market restarts retain that activation boundary;
  populated Markets recover from their latest Candle, bounded by activation.
  Existing pending recovery and live guards remain authoritative before either.
- Every broker acquisition carries the stored `broker_symbol_id` as
  `expected_symbol_id`. A remapped broker name must fail before fetching or
  subscribing; removal releases the original bound subscription ID.
- Live and recovery writes carry the runtime's local `symbol_id` as `market_id`.
  Storage locks that identity for each batch; a deleted/recreated symbol pair
  cannot receive writes from an old in-flight consumer or recovery request.
- `app/broker_client.py` adapts historical trendbars and stream control;
  `app/db_client.py` wraps the shared accessor client. Keep broker and storage
  query parameter conventions at these boundaries.

History configuration is described in [config context](../config/CONTEXT.md).
For parsing changes, also inspect indicator-api and realtime-service consumers; storage
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

## Explicit history downloads

`app/history/` owns one-time download acceptance, execution, notification retry, and
shutdown recovery. `app/http_api.py` exposes `/history-downloads` and `/health` on
`INGESTION_API_PORT` (8000). The same process runs live ingestion and the history
queue; readiness stays false until dependency initialization succeeds.

The accessor freezes each request's source and upper boundary and fences all
insert-only pages with owner/revision/cursor. The worker scans complete daily M1
windows backwards, includes the requested UTC date, and counts actual inserted
candles. Empty windows do not imply exhaustion. Each attempt is limited to 3660
windows; reaching that budget fails with a resumable explanation. Only reaching
the Unix epoch can complete an undersupplied count with an availability reason.
Explicit cancellation fences writes immediately. Shutdown releases owned work to
queued where possible; interrupted processes recover after the 120-second lease.
The worker renews leases every 30 seconds during broker retrieval. Completion waits
for the accessor to refresh aggregates for inserted history.

History invalidations use Redis `history:downloads:events`, field `event` containing
JSON `historyDownloadChanged` with `market_id`, `job_id`, and `revision`. Failed
publications remain queued, including terminal changes. Startup and recovery
reliably publish a global `historyDownloadsResnapshot` hint so every subscribed
Market rereads authoritative state, including jobs outside recent-list limits.
Finished worker tasks remain owned until their final snapshot has been queued
for notification (or their deleted job returns 404). The browser reads after
change hints and WebSocket reconnect; closing it never cancels work.
