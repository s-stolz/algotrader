# Broker Service Context

Adapts cTrader commands and market data to REST and Redis. Shared timestamps,
Candle/Tick fields, and stream names are in [root context](../CONTEXT.md).

## Seams and Gotchas

- `app/application/interfaces.py` defines broker ports;
  `app/infrastructure/ctrader_client.py` owns authentication, cTrader requests,
  protobuf mapping, history, and live event handling. For Order/Position/Deal
  changes, inspect both route contracts and this adapter.
- Order placement shape spans OpenAPI schema, `app/api/validation.py`, route
  code, and cTrader request construction; keep them aligned.
- `stream_registry.py` and `trendbar_stream_registry.py` under infrastructure
  own Tick and Candle stream lifecycles. Webserver owns subscriber reference
  counts; start/stop changes often cross that boundary.
- `redis_streams_publisher.py` owns publication. Parsing consumers are webserver,
  ingestion, and indicator-api; use the [contract map](../docs/agent/CONTRACT-CHANGES.md)
  for payload or Timeframe changes.
- Normalize cTrader symbol names to uppercase before broker calls.

For runtime/configuration usage, read [README.md](README.md).

## Verification

Use `make test broker-service`. Stream changes need registry behavior and affected
consumer parsing/lifecycle checks.
