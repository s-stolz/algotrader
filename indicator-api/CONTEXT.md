# Indicator live Candle context

**Live Indicator input:** the existing timestamp and OHLCV values of a Redis
Candle. Publication continuity does not become an Indicator field or parameter.

**Publication continuity:** backend delivery-session metadata. Legacy and enriched
Candles remain valid inputs; a session change does not rebuild an active Indicator.

For compatibility, recovery scope and upgrade order, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
