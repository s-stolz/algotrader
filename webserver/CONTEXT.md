# Webserver Context

Python WebSocket bridge between frontend clients, broker-service, indicator-api,
and Redis streams.

## Owned Interfaces

- Frontend WebSocket protocol for subscribe/unsubscribe commands and live update
  messages.
- Redis Candle and Indicator stream consumption, expansion, and fanout.
- Source stream reference counting and subscription lifecycle.
- HTTP adapters for broker-service and indicator-api stream start/stop calls.

## Key Modules

- `main.py`: process entrypoint, WebSocket server, health server, message routing.
- `app/subscription_manager.py`: client registration, subscription refcounts,
  broker source dependencies, indicator stream metadata, and fanout.
- `app/redis_consumer.py`: Redis stream consumption and compact-to-expanded
  message parsing.
- `app/broker_client.py`: broker-service stream start/stop HTTP adapter.
- `app/indicator_api_client.py`: live indicator stream start/stop HTTP adapter.

## Contracts

Frontend to webserver messages are flat JSON objects:

- `{"type": "subscribeCandles", "symbol": "EURUSD", "timeframe": "M1"}`
- `{"type": "unsubscribeCandles", "symbol": "EURUSD", "timeframe": "M1"}`
- `{"type": "subscribeIndicator", "symbol": "...", "timeframe": "...", ...}`
- `{"type": "unsubscribeIndicator", "symbol": "...", "timeframe": "...", ...}`

Webserver to frontend live updates are flat JSON objects:

- `candleUpdate` with expanded candle fields.
- `indicatorUpdate` with `clientIndicatorId`, `streamId`, `timestamp_ms`, and `values`.

- Uses the Redis stream names and compact candle fields defined in root
  `CONTEXT.md`.
- Expands Redis candle payloads before broadcasting to frontend clients.
- Source streams are reference counted by `SubscriptionManager`.

## Change Triggers

- `SubscriptionManager` is the owner of subscription lifecycle. It currently
  embeds key-string grammar and rollback behavior.
- Add tests before changing duplicate subscription handling, disconnect cleanup,
  source dependency counts, or indicator parameter sharing.
- If WebSocket messages change, update `frontend/CONTEXT.md` and
  `frontend/test/utils/websocketService.spec.ts`.
- If Redis Candle parsing changes, inspect `broker-service`, `ingestion-service`,
  and `indicator-api` live parsing.

## Verification

There is no dedicated first-party webserver test suite yet. New tests should cover
subscription lifecycle and Redis fanout without requiring live Redis or broker
network calls.
