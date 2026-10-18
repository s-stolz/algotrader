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
- `ctrader_protocol.py` bounds protocol-response silence on the Twisted reactor;
  heartbeats keep closed Markets connected.
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

# Broker historical data context

Broker adapts broker-available historical Candles for ingestion. The authoritative
[historical contract](HISTORY.md) defines interval completion and pagination.

**Completed history interval:** A finite requested interval for which the broker
has exhausted available provider history and delivered verified completion.
It can contain zero Candles; market inactivity is not a retrieval failure.

**Partial historical delivery:** Candles received before failure or without verified
completion. Their presence does not establish a completed history interval.

**Publication session:** uninterrupted live Candle delivery on a stable Redis
stream, identified by restart-safe per-message continuity. Its identity changes
across transport interruptions, known publication loss and stream recreation,
never ordinary silence.

**Publication loss:** a dropped queued Candle or failed/uncertain Redis publication.
The broker can remain connected while its publication session is interrupted.

**Connection health:** successful current broker connectivity/authentication. It
does not establish completed historical recovery.

For subscription restoration, queued-event ordering and consumer compatibility,
read [live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
