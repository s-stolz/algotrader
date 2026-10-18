# Broker historical data context

Broker adapts broker-available historical Candles for ingestion. The authoritative
[historical contract](HISTORY.md) defines interval completion and pagination.

**Completed history interval:** A finite requested interval for which the broker
has exhausted available provider history and delivered verified completion.
It can contain zero Candles; market inactivity is not a retrieval failure.

**Partial historical delivery:** Candles received before failure or without verified
completion. Their presence does not establish a completed history interval.
