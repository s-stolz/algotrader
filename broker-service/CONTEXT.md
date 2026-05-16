# Broker Service Context

FastAPI service that adapts cTrader Open API into broker commands, market data
queries, and Redis stream publication.

## Owned Interfaces

- Broker REST routes for accounts, orders, positions, deals, symbols, trendbars,
  and stream control.
- cTrader adapter interface for broker commands, market data, auth state, and
  protobuf mapping.
- Redis Tick and Redis Candle stream publication.
- Broker-facing Symbol normalization and timestamp handling.

## Key Modules

- `app/main.py`: FastAPI application and router registration.
- `app/settings.py`: typed environment settings and cTrader credentials.
- `app/api/routers/`: HTTP routes for accounts, orders, positions, deals,
  symbols, trendbars, and stream control.
- `app/api/validation.py`: manual request validation helpers.
- `app/api/serialization.py`: domain-to-JSON helpers.
- `app/application/interfaces.py`: broker, market data, publisher, and stream
  registry protocols.
- `app/application/services/`: thin use-case modules used by routers.
- `app/domain/`: value objects and broker domain models.
- `app/infrastructure/ctrader_client.py`: cTrader client, auth state, request
  construction, history fetches, and live event handling.
- `app/infrastructure/stream_registry.py`: tick stream lifecycle.
- `app/infrastructure/trendbar_stream_registry.py`: live candle stream lifecycle.
- `app/infrastructure/redis_streams_publisher.py`: Redis stream publishing.

## Contracts

- Broker historical trendbar routes use `fromTs` and `toTs` query parameters.
- Broker API timestamps follow the root `CONTEXT.md` transport contract.
- Publishes live tick and candle Redis streams defined in root `CONTEXT.md`.
- cTrader symbol names are normalized to uppercase before broker calls.

## Change Triggers

- `BrokerPort` is broad and `CtraderClient` is the main concrete adapter. When
  changing Order, Position, Deal, or Account behavior, check both route contracts
  and cTrader protobuf mapping.
- Order placement request shape is currently spread across OpenAPI schema,
  validation, route code, and cTrader request construction.
- Stream lifecycle is split between broker registries and webserver subscription
  lifecycle. Changes often affect both services.
- If Redis Tick, Redis Candle, or Timeframe behavior changes, use
  `docs/agent/CONTRACT-CHANGES.md`.

## Verification

- Broker tests: `make test broker-service`.
- Stream lifecycle changes should include registry tests and consumer contract
  checks where available.
