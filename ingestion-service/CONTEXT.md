# Ingestion historical data context

Ingestion selects historical intervals and stores broker-returned Candles.
Its consumer follows the broker's [historical contract](../broker-service/HISTORY.md).

**Closed M1 Candle:** A Candle whose UTC minute ended before the frozen history
request boundary. The current open minute is excluded from ingestion history.

**Completed empty history:** A successfully verified interval with no
broker-available Candles. It finishes normally, including during market closures.

**Partial historical delivery:** An unsuccessful download even when some Candles
arrived. It cannot count as successful backfill; durable restart recovery is a
separate operation beyond this transport contract.


## Authoritative Historical Correction

Startup and reconnect include the last stored M1 Candle, bounded by the existing
five-year history policy frozen for the service instance. Empty Markets use that
inclusive boundary. Even a recent last stored Candle is fetched again: recency
does not establish that its live OHLCV was final.

Backfill validates the completed broker interval before using the shared
historical-write contract. Ordinary live callbacks retain insert-only behavior.
Read [Candle persistence](../docs/contracts/candles.md) for request bounds,
partial-commit replay, compressed storage, and higher-Timeframe refresh semantics.
The opt-in `tests/test_history_integration.py` scenario needs an isolated accessor
and real Timescale storage; a skipped test is missing acceptance evidence.
