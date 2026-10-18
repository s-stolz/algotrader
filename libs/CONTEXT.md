# Shared Libraries Context

`db_accessor_client` owns matching synchronous and asynchronous HTTP transports.
Both expose ordinary `insert_candles` and authoritative `write_historical_candles`;
read [Candle persistence](../docs/contracts/candles.md) before changing these
contracts. Preserve interval and exchange identity, and propagate failed writes.

## Pending recovery

**Pending recovery** means unfinished history retrieval for a logical
Market/account/M1 source. It is not general historical completeness. For source
identity, conditional progress/completion and protected startup obligations, read
the [recovery contract](../docs/contracts/recovery.md).
