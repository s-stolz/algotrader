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
