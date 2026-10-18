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
