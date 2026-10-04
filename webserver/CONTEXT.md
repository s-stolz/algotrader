# Webserver Context

Python WebSocket bridge between frontend clients, broker-service, indicator-api,
and Redis streams.

## Ownership

`app/subscription_manager.py` owns client subscriptions, source dependency counts,
rollback, and fanout. `app/redis_consumer.py` expands Redis payloads; `main.py`
routes WebSocket messages. Broker and indicator HTTP adapters control upstream
stream start/stop. Shared Redis fields and timestamps live in
[root context](../CONTEXT.md).

## Contracts

Frontend to webserver messages are flat JSON objects:

- `{"type": "subscribeCandles", "symbol": "EURUSD", "timeframe": "M1"}`
- `{"type": "unsubscribeCandles", "symbol": "EURUSD", "timeframe": "M1"}`
- `{"type": "subscribeIndicator", "symbol": "...", "timeframe": "...", ...}`
- `{"type": "unsubscribeIndicator", "symbol": "...", "timeframe": "...", ...}`

Webserver to frontend live updates are flat JSON objects:

- `candleUpdate` with expanded candle fields.
- `indicatorUpdate` with `clientIndicatorId`, `streamId`, `timestamp_ms`, and `values`.

Webserver to frontend control messages are flat JSON objects:

- `subscribed` after candle subscription succeeds.
- `indicatorSubscribed` with `clientIndicatorId` and `streamId` after indicator
  subscription succeeds.
- `indicatorUnsubscribed` after indicator unsubscription succeeds.
- `error` with an `error` string when message handling fails.

Source streams are reference counted; upstream streams are shared across clients.

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
counts, and rollback using controlled Redis/broker adapters. Webserver tests are
not included in the root `make test` target; run them from this service directory
with its Python environment (`python -m unittest discover -s tests`).
