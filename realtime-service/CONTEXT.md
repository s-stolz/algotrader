# Realtime Service Context

Python WebSocket bridge between frontend clients, backtester, broker-service, indicator-api,
and Redis streams.

## Ownership

`app/subscription_manager.py` owns client subscriptions, source dependency counts,
rollback, and fanout. `app/redis_consumer.py` expands Redis payloads; `main.py`
routes WebSocket messages. Broker and indicator HTTP adapters control upstream
stream start/stop. Shared Redis fields and timestamps live in
[root context](../CONTEXT.md).

## Contracts

Frontend to realtime-service messages are flat JSON objects:

- `{"type": "subscribeCandles", "market_id": 1, "timeframe": "M1"}`
- `{"type": "unsubscribeCandles", "market_id": 1, "timeframe": "M1"}`
- `{"type": "subscribeIndicator", "market_id": 1, "timeframe": "...", ...}`
- `{"type": "unsubscribeIndicator", "market_id": 1, "timeframe": "...", ...}`

Realtime service to frontend live updates are flat JSON objects:

- `candleUpdate` with `market_id` and expanded candle fields.
- `indicatorUpdate` with `market_id`, `clientIndicatorId`, `streamId`, `timestamp_ms`, and `values`.
  Optional `replay: true` marks a corrected historical point. Consumers merge it
  into loaded history and redraw without rewinding the live tail. Redis uses
  `replay: "1"`; ordinary updates omit the marker.

Realtime service to frontend control messages are flat JSON objects:

- `subscribed` after candle subscription succeeds.
- `indicatorSubscribed` with `clientIndicatorId` and `streamId` after indicator
  subscription succeeds.
- `indicatorUnsubscribed` after indicator unsubscription succeeds.
- `error` with an `error` string when message handling fails.

A positive `market_id` is mandatory for all live subscription commands. Stored
Market identity supplies the symbol and exchange; client-supplied labels are not
authority. Only Broker Markets bound to the configured cTrader account and
environment may acquire live sources. Acquisition refreshes broker instrument
verification and passes the frozen broker ID to stream start/stop; source
reference counts include that ID. Reusing an indicator session still verifies all
of its source identities. Custom Markets remain historical-only,
even when their symbol matches a connected broker instrument.

Source streams are reference counted; upstream streams are shared across clients.
Indicator dependencies come from indicator-api's `GET /indicators/{id}` metadata:
use `inputs` when present, otherwise the chart Market. Resolve every dependency
to one Broker Market in the same exchange/account/environment before acquiring
any source; missing or ambiguous inputs reject the whole subscription. Each subscription retains
all dependencies; partial startup rolls them back, and disconnect releases them.
Indicator subscription mutations are serialized so concurrent clients share one
upstream indicator session. Install the metadata endpoint before this consumer.

## Backtest delivery

`app/backtest_events.py` owns the independent backtest stream reader and browser
fanout. Every subscribed browser receives events; gateway instances do not share a
worker consumer group. Establish a stream cursor before reporting connected,
and report Redis disconnection even when browser sockets remain open. Browsers
refresh authoritative snapshots on subscription/reconnection, so old gateway
messages need not be replayed. Backtest policy remains in backtester-api.

Stage updates restore the latest Redis progress snapshot on subscription and
reconnect; they do not request saved-result refreshes. See
[run progress](../docs/contracts/backtests.md#run-stage-progress).

For `subscribeBacktests`, `unsubscribeBacktests`, and the outbound event
shapes, read [real-time delivery](../docs/contracts/backtests.md#real-time-delivery-and-recovery).

## History download delivery

`subscribeHistoryDownloads` and `unsubscribeHistoryDownloads` require `market_id`.
Only Broker Markets bound to the configured connection may subscribe. This
checks stored eligibility without requiring the broker to be online, so failures
and cancellation remain visible during broker outages. `historyDownloadChanged` carries
`market_id`, `job_id`, and `revision`; clients read authoritative job snapshots
from ingestion rather than treating events as state.

`historyDownloadsConnection` carries `market_id` and `connected`. Browsers
refresh snapshots on subscription and reconnection, including Redis recovery
while the browser socket stays open. The bridge establishes its cursor on
`history:downloads:events` before reporting connected. Each Redis row has an
`event` JSON field. Every gateway reads independently and fans out only to
subscribers for the event's Market. A global
`{"type":"historyDownloadsResnapshot"}` producer event repeats the connected
signal for every subscribed Market, including sockets already connected. This
recovers missed terminal changes without relying on bounded recent-job replay.

## Change Triggers

- Add tests before changing duplicate subscription handling, disconnect cleanup,
  source dependency counts, or indicator parameter sharing.
- If WebSocket messages change, update `frontend/CONTEXT.md` and
  `frontend/test/utils/websocketService.spec.ts`.
- If Redis Candle parsing changes, inspect `broker-service`, `ingestion-service`,
  and `indicator-api` live parsing.

## Verification

Start with `tests/test_redis_consumer.py` for Redis parsing. Subscription lifecycle
changes also need coverage for duplicate subscriptions, disconnect cleanup, source
counts, and rollback using controlled Redis/broker adapters. Run `make test realtime-service`;
the root backend gate includes this suite.

# Realtime service Candle transport context

**Public Candle:** expanded OHLCV plus `timestamp_ms` delivered to WebSocket
subscribers. Broker continuity is transport metadata, excluded from this shape.

**Publication continuity:** backend session identity on Redis Candles. Chart fanout
accepts both legacy and enriched rows; it does not trigger historical refresh.

For the producer/consumer contract and protected upgrade sequence, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
