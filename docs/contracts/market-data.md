# Market sources and historical downloads

A Market's durable identity is its local `symbol_id`. Its `source_type` determines
whether broker collection is supported. A historical download is accepted,
one-time work; it is not a permanent history-depth setting on the Market.

## Source identity

- **Broker Market:** `source_type: broker`, `broker_provider: ctrader`, a string
  `broker_account_id`, `broker_environment: demo | live`, and a positive
  `broker_symbol_id`. The broker instrument ID is not the local Market ID.
- **Custom Market:** `source_type: custom`, with no broker binding. CSV uploads,
  historical charts, historical indicators, and backtests remain available;
  broker subscriptions and history downloads are unavailable.

The normalized `(symbol, exchange)` pair remains unique. Source and broker binding
are immutable after creation. Broker symbol/exchange labels also cannot change to
represent another instrument. Other specifications remain editable. A different
source or instrument requires a separate Market.

Accessor creation verifies Broker identity against broker-service's configured,
authorized connection and instrument catalogue before its storage transaction.
Validation fails when the requested account, environment, ID, symbol, or broker
label differs. Unavailable broker verification is a failure, not permission to
save an unverified binding. Database constraints preserve the accepted source.
The broker service does not depend on the accessor for this verification.

`live_start_ms` is an immutable, server-selected UTC minute boundary recorded when
a Broker Market is created. It marks the beginning of live-collection recovery;
it is not the user's requested historical start. Custom Markets have no such
boundary. Existing Markets become Custom in V023, retaining their IDs, metadata,
and Candles. This intentionally disables automatic broker activity for old rows
whose provenance cannot be inferred safely.

`POST /candles/upload` is the Custom-only CSV boundary. Ordinary internal Candle
writes remain separate because broker live collection and recovery still write
Broker Markets. Hiding an upload action in the frontend is not the eligibility
check.

## Source-aware collection and live transport

Ingestion reconciles stored Markets every two seconds. Only Broker Markets bound
to its configured account/environment enter its live runtime. New eligible
Markets start without a service restart; removed Markets release their tasks and
subscription. An empty Market starts recovery at `live_start_ms`; a populated
Market uses the later of that boundary and its latest stored M1 Candle. Existing
pending recovery and live write guards retain priority over either choice.
Skipping historical download therefore still collects new candles, without
applying a global 90-day backfill. See [pending recovery](recovery.md).

Browser live commands require `market_id`. The gateway resolves symbol/exchange
from that stored Market and refuses Custom sources before acquiring a broker
subscription. Indicator live requests enforce the same rule independently.
Every multi-input indicator dependency must resolve to one eligible Broker Market
in the same exchange/account/environment. Missing or ambiguous inputs reject the
subscription before any dependency is acquired. Before each acquisition, the
stored instrument ID and name are verified against the broker's refreshed
catalogue, including every basket input and reused indicator session. Broker
stream/history requests carry `expected_symbol_id`; a remapped name is rejected
instead of silently switching instruments. Stream cleanup retains the original
ID rather than resolving a changed name. Historical calculations remain available
for Custom Markets.

Candle and indicator fanout includes `market_id`. Symbol text is not sufficient
to route a live update: a Custom EURUSD dataset must not receive a Broker EURUSD
stream. Wire shapes live in [realtime context](../../realtime-service/CONTEXT.md).

## Download requests

Ingestion owns public commands and lifecycle policy. The accessor owns durable
transactions and the shared client preserves their conditional results. The
frontend reaches ingestion through `/api/ingestion`:

| Endpoint | Meaning |
| --- | --- |
| `POST /history-downloads` | Accept an idempotent request for a Broker Market. |
| `GET /history-downloads?market_id=...` | Read a bounded recent job list. |
| `GET /history-downloads/{id}` | Read one authoritative snapshot. |
| `POST /history-downloads/{id}/cancel` | Stop further accepted writes; preserve completed pages. |
| `POST /history-downloads/{id}/retry` | Resume failed/cancelled work from its saved cursor. |

Creation accepts a UUID `request_id`, positive `market_id`, and exactly one of:

- `start_date`: an ISO `YYYY-MM-DD` date, interpreted as inclusive UTC midnight,
  on or after 1970-01-01 and not in the future.
- `candle_count`: 1–1,000,000 additional stored one-minute candles. This counts
  candles, not elapsed minutes or the currently selected chart timeframe.

Acceptance freezes the source snapshot and `end_exclusive_ms` under the Market
lock. For a populated Market this upper boundary is its oldest stored M1 Candle;
for an empty Market it is the beginning of the current UTC minute. Downloading
extends older history and excludes the open Candle. Date requests must precede
the frozen upper boundary. Repeated acceptance with the same request ID and
selector returns the accepted job; conflicting reuse is rejected.

`GET /markets/id/{market_id}/coverage` returns `market_id`,
`oldest_timestamp_ms`, `latest_timestamp_ms`, and raw-M1 `candle_count`.
Empty timestamps are null and count is zero. These bounds do not assert that
all intervals between them are present. This download flow extends the older
prefix; it does not repair internal gaps or refresh existing OHLCV.

## Durable execution and cancellation

V024 stores jobs with statuses `queued`, `downloading`, `completed`, `failed`, and
`cancelled`. Only one queued/downloading job may exist per Market. Deletion is
blocked while such work exists. Immutable source identity also prevents an
accepted job from writing into a newly relabelled broker instrument.

Snapshots retain the original selector (`start_ms` or `candle_count`), frozen
`source_snapshot`, upper boundary, backward-exclusive `cursor_ms`,
`fetched_count`, `inserted_count`, `revision`, timestamps, and nullable
`failure_reason` / `availability_reason`. Public snapshots omit worker ownership
and lease fields. Closing the dialog or browser has no effect on the job.

Accessor `/history-download-jobs` endpoints provide create/read/list plus
`/{id}/claim`, `/heartbeat`, `/pages`, `/transition`, `/cancel`, and `/retry`.
Claims hold a renewable lease; page and transition operations require matching
owner and revision. A stale operation returns a null receipt and must not advance
local progress. One transaction checks the lease/cursor, inserts previously absent
Candles, and advances the cursor and counters. Replaying a lost receipt cannot
overwrite OHLCV or double-count progress. This insert-only path is deliberately
separate from [authoritative recovery upserts](candles.md).

Workers fetch verified finite M1 windows of at most one day, moving backwards.
They sort and deduplicate records and retain only the closed requested interval.
Count requests stop when `inserted_count` reaches their target; empty weekend or
holiday windows do not imply exhaustion. An attempt pauses as `failed` after
3,660 windows with an explicit retry instruction; retry keeps its cursor. Only
reaching the supported epoch boundary with fewer candles marks count completion
with an availability explanation. No synthetic candles fill missing intervals.

Before completed status, storage refreshes affected historical aggregate buckets,
including those outside normal rolling refresh windows. Timescale refresh calls
use a separate autocommit connection while the Market/job locks remain held;
they cannot run inside the job transaction. Refresh failure prevents a false
completed result. Already downloaded raw Candles remain present on
failure or cancellation.

Cancellation takes the storage lock and fences subsequent writes before returning
`cancelled`; an in-flight transaction that committed earlier remains valid. The
worker then stops its pending retrieval. Retry preserves confirmed progress and
rejects a competing active request. Shutdown requeues owned work when possible;
a crash leaves its lease recoverable after expiry. The default lease is 120 seconds
with worker heartbeats every 30 seconds. Neither shutdown nor browser closure is
an explicit cancellation.

## Browser delivery and recovery

Ingestion publishes revision hints to Redis `history:downloads:events`, with an
`event` JSON field containing `historyDownloadChanged`, `market_id`, `job_id`, and
`revision`. Failed publications retain the latest pending revision for retry,
including terminal changes. Producer startup and publication recovery also send
a global `{"type":"historyDownloadsResnapshot"}` event, retried until publication
is confirmed. This refreshes every subscribed Market regardless of job creation
order or bounded recent-job lists, covering terminal changes committed before a
producer crash. Events are invalidations, not authoritative job state.

Browsers use `subscribeHistoryDownloads` / `unsubscribeHistoryDownloads` with
`market_id` on the existing WebSocket. The gateway sends
`historyDownloadsConnection` with `market_id` and `connected`. It establishes a
concrete stream cursor before reporting connected, and signals Redis interruptions
even while the browser socket stays open. A producer resnapshot event sends
`connected: true` again to every subscribed Market without requiring a gateway
or browser reconnect. Browsers refresh on every such signal, not only a
false-to-true transition, as well as on subscription and change hints. No separate browser polling loop
or browser-owned download worker is required.

## Verification boundaries

Source validation, websocket isolation, job-state transitions, and page selection
have focused service tests. Real PostgreSQL/Timescale checks are required for
transaction races, fencing, insert-only replay, deletion locks, and historical
aggregate visibility. Real process checks must cover interruption, resume,
cancellation, and notification recovery. Skipped environment-dependent tests are
not evidence that those paths passed.
