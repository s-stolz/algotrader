# TimescaleDB Context

Raw M1 Candles retain their `(symbol_id, timestamp_utc)` primary key. Historical
correction uses native upsert without a schema change. Compression needs
TimescaleDB 2.11+ / PostgreSQL 14+ for this DML. Read
[Candle persistence](../docs/contracts/candles.md) for replay and aggregate-refresh
semantics and isolated live verification. Existing aggregate policies have rolling
windows: corrections older than those windows need an explicit materialized-bucket
refresh to appear in higher Timeframes.

## Pending recovery

**Pending recovery** means unfinished history retrieval for a logical
Market/account/M1 source. It is not general historical completeness. For source
identity, conditional progress/completion and protected startup obligations, read
the [recovery contract](../docs/contracts/recovery.md).

**Live write guard:** the durable pre-batch confirmed boundary for an unconfirmed
live Candle write. Partial commits and lost receipts cannot hide it behind a
newer latest Candle; normal successful live writes retire it without scheduling
history. See the [guard contract](../docs/contracts/recovery.md#durable-live-write-guards).
