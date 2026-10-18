# Candle persistence

`POST /candles` is ordinary live M1 persistence: the existing primary key
`(symbol_id, timestamp_utc)` makes inserts duplicate safe, and conflicts leave
stored OHLCV unchanged. A later stale live retry cannot undo historical values.

`POST /candles/historical` is authoritative historical M1 persistence. Shared
sync/async `write_historical_candles` sends the Market, Candles, and inclusive
`start_ms` / `end_ms` requested interval. All timestamps must be minute aligned,
inside that interval, and closed. An interval reaching the current UTC open
minute is rejected, as is an ambiguous Market without its exchange. Validation
rejects the entire request before any writes. Missing Market returns 404.

Only supplied OHLCV is inserted or replaced. Omitted timestamps are retained;
rows outside the interval are untouched. Repeated timestamps use the last supplied
value. PostgreSQL upsert and insert-ignore resolve concurrent live/history writes
through the existing primary key regardless of arrival order. Replaying history
after an uncertain HTTP result is safe. Different historical payloads for the same
row follow commit order; no historical source version is inferred.

The accessor commits batches of at most 4000 rows. An error can follow earlier
committed batches, so callers propagate failures and replay the requested interval;
a response failure never proves that nothing committed. The response's
`written_candles` counts upserted rows (including replacements), and
`total_candles` counts input rows. Ordinary live response fields are unchanged.

No schema change is required. Native upsert of compressed Candles requires
TimescaleDB 2.11+ and PostgreSQL 14+; the deployed Compose image uses PostgreSQL 17.
See [Timescale compression DML support](https://github.com/timescale/docs/blob/latest/api/compression/index.md).
Higher Timeframes continue through existing continuous aggregates and direct
bucketing. Updates invalidate aggregate buckets; refresh existing materialized
buckets using their policies, or explicitly refresh an older corrected interval
outside the rolling policy window. This contract does not refresh open charts or
Indicator state.

Live checks: use a disposable database named `vibe9_*` with Timescale installed,
then set `HISTORY_TEST_DATABASE_URL=postgresql+asyncpg://.../vibe9_test` and run
`python -m unittest discover -s database-accessor-api/tests -p 'test_*.py'`
with `PYTHONPATH=database-accessor-api:libs/algotrader_logger` and accessor dependencies.
Without the URL, live tests are explicitly skipped. They exercise actual API,
concurrent sessions, compressed chunks, replay, and aggregate refresh. Every test
owns and removes a unique schema; never point acceptance tests at real history.

For ingestion-level acceptance, run an accessor from this checkout against the
same disposable Timescale database. Set `HISTORY_TEST_ACCESSOR_URL` to its loopback
HTTP URL and run the ingestion suite with its own dependencies and
`PYTHONPATH=ingestion-service:libs/db_accessor_client:libs/algotrader_logger`.
The scenario creates and deletes only its uniquely named synthetic Market. It
uses the actual broker completion parser, accessor HTTP client, and database
writes; controlled upstream responses include incomplete download and a lost
receipt after a committed historical chunk. A plain run without this URL skips
these two live scenarios explicitly.
