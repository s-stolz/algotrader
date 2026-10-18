# Webserver Candle transport context

**Public Candle:** expanded OHLCV plus `timestamp_ms` delivered to WebSocket
subscribers. Broker continuity is transport metadata, excluded from this shape.

**Publication continuity:** backend session identity on Redis Candles. Chart fanout
accepts both legacy and enriched rows; it does not trigger historical refresh.

For the producer/consumer contract and protected upgrade sequence, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
