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

## Market identity fencing

Ordinary and authoritative historical JSON batches accept an optional
`market_id`. Source-aware ingestion supplies the local Market ID captured by its
runtime state, together with symbol and exchange. The accessor bypasses its name
cache, locks that exact row, and verifies the supplied identity before each batch
of at most 4000 rows. It revalidates after each batch commit. A deleted ID returns
404; a symbol/exchange mismatch returns 409. Neither case falls back to another
Market created later with the same name.

Legacy requests that omit `market_id` retain their name-based behavior.
`POST /candles/upload` first verifies Custom eligibility and binds that Market's
ID even when an older CSV payload omits it; a conflicting supplied ID is rejected.
This prevents an in-flight upload or broker write from crossing into a replacement
Market after deletion. Earlier committed batches retain the partial-write
semantics above. See [Market sources](market-data.md#source-identity).

## Storage and acceptance

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

## Historical Candle streams

`GET /candles/{symbol}/stream` requires `timeframe`, inclusive `start_ms`, and
exclusive `end_ms`. `exchange` resolves the Market; an immutable positive
`market_id` can identify a saved Run's Market just as for ordinary Candle reads.
The response is `application/x-ndjson`: `{"type":"candles","candles":[...]}`
frames contain at most 1024 ascending expanded Candles, followed by exactly one
`{"type":"complete"}` frame. EOF without completion is a failed read. Stream
consumers must not treat a received prefix as complete historical data.

The accessor owns a database cursor and session for the stream, closing both on
completion, failure, or disconnect. Row conversion and JSON encoding are bounded
by the batch size, with scheduling opportunities between batches. Higher
Timeframes preserve aggregate selection and empty-aggregate bucketing fallback.
No pagination request loop or resume token is exposed. Clients close the stream
when downstream consumers stop and request identity encoding to avoid compression
buffering. Proxies must preserve streaming and propagate connection closure.
Existing bulk JSON Candle endpoints and persistence contracts are unchanged.

Streaming checks: `tests/test_candle_stream.py` covers bounded scheduling and
cursor cleanup. Set `RUN_CANDLE_STREAM_HTTP_TESTS=1` for the loopback HTTP
responsiveness/disconnect test with 362,117 fixture Candles. Set
`CANDLE_STREAM_TEST_DATABASE_URL` to a disposable database named
`equity_stream_test` for real cursor and bulk/stream parity checks. Run from
`database-accessor-api/` with `.venv/bin/python -m unittest discover -s tests
-p test_candle_stream.py`. These opt-in checks never use production tables.

## Forward Candle pages

`GET /candles/{symbol}?from_start=true` returns the first `limit` candles in
ascending order within inclusive `start_ms` and exclusive `end_ms`. This mode
requires both bounds and a limit of 1–500. Omitted or false `from_start` preserves
the existing latest-first selection (returned chronologically) for limited reads.
An underfilled page means no more stored candles exist inside the requested bounds;
it does not assert historical completeness or that ingestion is current.

`app/candle_pages.py` uses raw M1 data and direct bucketing for higher timeframes,
so missing aggregate retention cannot skip the prefix of a forward page. Chart
paging passes full bucket boundaries to avoid partial first bars. No storage or
streaming contract changes are required.
