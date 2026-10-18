# Ingestion history context

**Closed M1 Candle:** a Candle whose UTC minute ended before the frozen history
request boundary. The current open minute is excluded from recovery.

**Completed empty history:** a successfully verified interval with no
broker-available Candles, including ordinary Market closures.

**Partial historical delivery:** an unsuccessful download even when some Candles
arrived; it cannot count as completed recovery.

**Recovery boundary:** inclusive beginning of broker history still to verify.

**Pending recovery:** durable unfinished work for a Market/account/M1 source.
Newer live rows and history-policy changes cannot erase it. It is not a general
completeness index or an inference from ordinary Market silence.

**Historical window:** a finite closed interval whose complete retrieval and
confirmed writes are required before advancing pending recovery.

For protected startup, triggers, concurrency/retry/shutdown obligations,
configuration, migration and real process acceptance, read the
[recovery contract](../docs/contracts/recovery.md). For authoritative correction,
compressed storage and partial-write replay, read
[Candle persistence](../docs/contracts/candles.md). Broker delivery completion is
owned by the [historical transport contract](../broker-service/HISTORY.md).
