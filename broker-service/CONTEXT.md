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
  heartbeats keep closed Markets connected. `/meta/health` exposes the container
  instance identity used to detect process restarts.
- `stream_registry.py` and `trendbar_stream_registry.py` under infrastructure
  own Tick and Candle stream lifecycles. Realtime service owns subscriber reference
  counts; start/stop changes often cross that boundary.
- `redis_streams_publisher.py` owns publication. Parsing consumers are realtime-service,
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

## Installation catalogue

`GET /connection` verifies the configured `ACCOUNT_ID` against the authorized
account and environment. `GET /setup/instruments/{broker_symbol_id}` verifies an
enabled instrument in that account and returns its immutable source binding.
The accessor uses this endpoint before creating a Broker Market; the frontend
uses it for verified prefills. Optional metadata may be absent. Display precision
is only `suggested_min_move`, and lot size is never a contract multiplier.
Account-scoped caches prevent equal names or broker IDs from resolving against
another account's catalogue. Local Market IDs remain distinct from broker IDs.

## Local authorization

`python -m app.onboarding authorize` handles initial browser authorization and
same-account reconnect without starting the API or a second refresh loop. See
[broker setup usage](README.md#local-browser-authorization). The terminal supplies
user-owned application credentials through environment variables. The callback
requires a browser-bound session and matching OAuth state. Missing or mismatched
state fails closed before code exchange; there is no pairing bypass. Real-provider
state echo behavior still needs manual demo-account acceptance.

Credential output is atomically written with mode `0600`, including actual issue
and expiry times. Redis token state binds client ID, account, and environment.
Reconnect requires the existing account ID and a stopped broker; the new state
replaces Redis explicitly. Runtime refresh uses compare-and-set, preventing an
in-flight old refresh from overwriting a reconnection. Existing unbound developer
token state is bound to its configured connection at the first startup.

Source-bound history and live acquisitions require `expected_symbol_id` from the
stored Market binding. Fresh catalogue resolution must match before any provider
history/subscription request; cleanup verifies the original subscription handle
instead of re-resolving a possibly renamed instrument. See [history contracts](HISTORY.md#bound-broker-instruments).
