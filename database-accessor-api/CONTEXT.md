# Database Accessor Context

The accessor owns Market resolution and persistence transactions. Ordinary live
Candle inserts in `app/crud.py` retain existing rows; authoritative closed M1
writes in `app/historical_candles.py` replace OHLCV using the same uniqueness key.
Read [Candle persistence](../docs/contracts/candles.md) before changing either
write path. `tests/test_historical_candles_postgres.py` verifies real Timescale
behavior through the API, including compressed history and concurrent writes.

## Pending recovery

**Pending recovery** means unfinished history retrieval for a logical
Market/account/M1 source. It is not general historical completeness. For source
identity, conditional progress/completion and protected startup obligations, read
the [recovery contract](../docs/contracts/recovery.md).
