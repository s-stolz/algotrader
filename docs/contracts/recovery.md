# Pending M1 recovery

A **recovery boundary** is the inclusive beginning of broker history still to be
verified. A **pending recovery** is accepted unfinished work for one logical
Market (`symbol_id`), broker `account_id`, and M1 source. It is not evidence of
historical completeness and does not infer outages from missing minutes.

Ingestion owns recovery policy. The accessor owns durable transactions; shared
sync/async clients preserve their conditional results. Candle authority and
partial-write behavior remain in [Candle persistence](candles.md).

## Persistence API

- `GET /recoveries/{symbol_id}?account_id=...` returns `{pending: record | null}`.
  A successful null means no pending work. HTTP/database failure propagates.
- `POST /recoveries/begin` accepts `symbol_id`, `account_id`, inclusive `start_ms`,
  inclusive closed `target_ms`, and `trigger`. An atomic upsert retains the least
  unfinished `next_ms`, extends the target, and increments `revision`. The record
  contains these fields plus an opaque `recovery_id`; the timeframe is always M1.
  A new record has a new identity even after a previous recovery completed.
- `POST /recoveries/advance` accepts source, `recovery_id`, `revision`,
  `expected_start_ms`, and `next_ms`. It returns `{updated: bool}`. Progress is
  conditional on all identity/revision/cursor fields matching the current row.
  Advancing to `target_ms + 1` deletes pending work; stale operations return false
  and must reload. New progress cannot exceed that target. An empty interval can
  begin at `target_ms + 1` and complete without retrieving an open Candle.

The begin target must precede the current UTC open minute. Market deletion
cascades pending work; Candle writes alone never change it. The primary key is
Market/account because M1 is the only recovery timeframe. No source subscription
or historical-completeness registry is introduced.

## Protected startup and handoff

Each Market starts independently. Before selecting a new latest-Candle boundary,
load existing pending work. Pending progress is authoritative even if a newer live
row exists or a rolling lookback has advanced. With no pending work, use the
latest stored M1 timestamp, bounded by the process's configured history boundary;
an empty Market uses that boundary inclusively.

Capture the Redis tail before starting the broker subscription. After subscription
setup succeeds, capture the closed historical target and durably begin/merge
pending recovery. Only then start consuming from that tail and allow live writes.
This covers history through subscription establishment, while Redis retains
messages arriving during setup/save. The ordinary consumer withholds its open
Candle. The open minute at subscription establishment is excluded from that
initial closed target. Before the first closed live batch can commit, durably
merge a handoff recovery beginning at that saved target plus one, extending
through the now-closed interval. This covers the tail's open minute even when no
later Redis update for that minute arrives. Before that first write, a crash can
only leave the previous latest boundary or already-saved pending work, so restart
preserves the same coverage. Boundary-read or save failure leaves this Market protected and retries;
other Markets and broker publication continue.

Live writes and historical recovery proceed concurrently after the save. The
reusable `request_recovery` operation closes the Market write gate, loads/merges
pending work, saves it, schedules recovery, and opens the gate. Startup and health
reconnect recovery share the same pending policy and historical worker. Additional
interruption triggers use this operation rather than choosing a new latest row
inside a historical retry.

## Live publication continuity

A **publication session** identifies uninterrupted live Candle delivery on one
stable `candles:{account_id}:{symbol}:{timeframe}` stream. Every newly published
Candle has the six existing `o,h,l,c,v,t` fields plus `continuity`, an opaque ASCII
`v1:` followed by 32 lowercase hexadecimal characters. Consumers must compare the
whole value, never derive account or Market identity from it. No stream discovery,
rotating keys, separate continuity stream, or continuity lookup is required.
Historical responses and public Candle/WebSocket fields retain their existing shape.

Broker transport identity is randomly initialized on each process start and
changed by the actual cTrader disconnect callback before dispatch to the asyncio
loop. Live event dispatch captures that identity. A dispatch delayed across the
change is discarded; subsequent history recovers it. The stream registry assigns
its own random publication identity at stream creation and after a changed
transport identity, stamping each Candle before queueing it. Already queued old
Candles retain their old identity; the FIFO writer publishes them before newer
queued sessions. A writer must never apply its current identity to an old item.
Elapsed time, missing Candles, weekends and holidays do not change identity.

After application authentication, cTrader accounts and spots are restored before
trendbars. Application/account authentication and subscription errors do not count
as success. Application authentication and subscription restoration retry actual
failures indefinitely with capped backoff. Another disconnect cancels stale work;
shutdown awaits it. A failed stream start removes its temporary registration so
a successful retry cannot duplicate handlers or return a dead placeholder stream.

Ingestion processes contiguous session runs in Redis order, including several
sessions in one XREAD. Before the first message of a new session can affect live
storage, it uses the same durable recovery operation as startup: close the write
gate, preserve/merge the old database boundary, freeze a closed target, then reopen
the gate. The first closed batch subsequently extends protection over the session
handoff's open minute. Additional changes during backfill merge a newer revision
and target while preserving the earliest unfinished cursor. Stale completion
cannot clear that newer work. Connection-health polling may request the same
operation, but message identity detects reconnects too brief for polling.

An open Candle from the prior session can contain partial pre-disconnect values.
After protection is saved, discard it and let authoritative history provide the
closed value. A failed protection save retains the unacknowledged batch, including
remaining session runs; no affected live write can precede the successful save.
A retry does not rewind already acknowledged earlier runs within that batch.

Missing, non-ASCII, unsupported-version or malformed continuity is **untrusted
live data**. Ingestion durably requests `invalid-continuity` recovery before
acknowledging/discarding those rows, never writes them as live Candles, and clears
any old open Candle. Historical retrieval recovers broker-available closed data.
If storage is unavailable, the cursor stays put and retries. This deliberately
keeps an old producer from silently bypassing protection. Webserver and Indicator
consumers accept legacy and enriched rows: they ignore transport continuity and
expose only their existing Candle/Indicator fields. They do not refresh chart
history or rebuild an existing live Indicator session.

Authentication, healthy containers and fresh live delivery establish connection
health only. Historical recovery succeeds only when the finite interval's broker
completion, authoritative writes and conditional progress all succeed. Empty
broker history during a closure completes normally; silence alone requests no work.

## Windows, retries, and shutdown

Recover at most one finite day per historical request. Buffer at most its possible
M1 Candles, require the broker completion record, then write authoritative batches.
Only confirmed complete retrieval and all confirmed writes allow conditional
progress. A failed later batch or lost write/progress receipt replays the unchanged
window; already committed upserts are safe. An older operation cannot advance or
clear a newer merge. Successfully empty windows advance normally, including
market closures. Never synthesize Candles or continually move a retry target.

Serialize historical work per Market and bound global requests using
`STARTUP_BACKFILL_CONCURRENCY`. Boundary and stream setup use their existing
startup concurrency settings. Release global capacity before capped exponential
backoff, retry actual failures indefinitely, and yield between windows so a
failing Market cannot occupy all recovery capacity while sleeping. A changed
clock cannot advance progress through an unclosed target.

Shutdown closes consumption, cancels/awaits owned startup/recovery/consumer tasks,
and drains in-flight synchronous storage HTTP operations before closing clients.
Pending work remains if shutdown interrupts retrieval, writes, or progress.
Concurrent shutdown callers wait for the same completed cleanup. Logs identify
Market/account/M1, interval, trigger, revision, retry delay, and completed windows;
connection URLs and credentials are not logged by startup/recovery policy.

## Configuration and upgrade

`ingestion.lookback_days` or quoted UTC `ingestion.start_date` selects the fresh
history boundary. Set the unused value to null, regenerate config, and restart
ingestion. The default remains five years (1825 days); a changed policy does not
clip accepted pending work. Expanding the policy does not audit older history
before an existing Market's latest Candle.

This branch's legacy schema bootstrap has no earlier ledgered migrations.
`timescaledb-init/migrations/V001__pending_recovery.sql` adds pending state without
changing existing Candles. `05-run-migrations.sh` applies it transactionally under
one session advisory lock and records a checksum in `schema_migrations`. Before
any pending SQL, it validates strict names, unique consecutive versions from V001,
and the presence/checksums of every applied migration. Applied versions must form
a consecutive inventory prefix. It executes the immutable snapshots used for
checksums, so concurrent deployment-file changes cannot alter the planned SQL.
Replay skips identical migrations; missing/renamed files, duplicate versions,
gaps and checksum drift fail without applying pending SQL. Applied SQL is
immutable; later changes require a new forward migration.

For existing volumes:

1. Stop ingestion before changing its storage or continuity contract. Preserve
   Redis streams and all pending rows; do not drain or delete real history.
2. Deploy the migration assets, then run
   `docker compose --env-file config/.env.shared exec -T timescaledb sh /docker-entrypoint-initdb.d/05-run-migrations.sh`.
   The runner uses `TIMESCALEDB_DB` (legacy default `finance_data`) and
   `POSTGRES_USER`; supply the database explicitly when the container uses another
   name. Fresh volumes run the script after legacy table initialization.
3. Deploy the compatible accessor/shared client and the webserver/Indicator
   consumers. Deploy/restart the continuity-producing broker while ingestion stays
   stopped. Retained legacy Redis rows may remain: protected startup snapshots the
   tail and recovers from the database boundary through subscription establishment;
   any legacy rows arriving after that tail follow the untrusted-data policy above.
4. Deploy the compatible ingestion consumer, regenerate history settings, and start
   it through protected startup. Confirm durable pending state before relying on
   fresh live delivery, then confirm history/progress completion. Do not activate
   an older ingestion consumer against this rollout: it cannot enforce continuity.
5. For rollback, keep ingestion stopped or use a continuity/recovery-aware version.
   Retain pending rows and the migration ledger. Do not revert the schema or delete real
   history. Restarting recovery-aware ingestion replays unfinished windows.

## Reproduce acceptance

Use only isolated loopback services and synthetic data. Real accessor transaction
checks use `HISTORY_TEST_DATABASE_URL` with a disposable `vibe9_*` Timescale
database; see [storage setup](candles.md). Run accessor tests from this checkout
with its dependencies and `PYTHONPATH=database-accessor-api:libs/algotrader_logger`.
The recovery tests exercise merge/completion races, stale cursor/revision/identity,
account isolation, validation, migration SQL, and durable reads after connection
recreation.

For real process acceptance, start this accessor against an **empty disposable**
Timescale database after applying the migration, plus a disposable Redis. Set
`RECOVERY_TEST_ACCESSOR_URL=http://127.0.0.1:<port>` and
`RECOVERY_TEST_REDIS_URL=redis://127.0.0.1:<port>/0`, then run
`python -m unittest discover -s ingestion-service/tests -p test_recovery_process.py -v`
with `PYTHONPATH=ingestion-service:libs/db_accessor_client:libs/algotrader_logger`.
The test starts controlled broker/dependency HTTP adapters and real child ingestion
processes. It kills ingestion before boundary save, after a protected live write,
and after historical writes before progress. The sessions phase first completes
startup, then delivers two rapid changed identities while health always stays up,
merges their work and kills ingestion with it pending. After restart with a one-day
lookback, it verifies a previously missing October 6 Candle and authoritative
October 18 values from supplied broker results, then resumed Redis live delivery.
Each phase verifies persisted Candles and pending state, without expecting one
Candle per calendar minute. It removes only its synthetic Market and stream.
No process or storage test may target real history. Missing environment variables
produce explicit skips, never evidence of acceptance.

For runner integrity acceptance, start an owned disposable Timescale container
named `vibe10r1-*`, set `RECOVERY_MIGRATION_TEST_CONTAINER` to that name and
`RECOVERY_MIGRATION_TEST_USER` to its synthetic PostgreSQL user, then run
`python -m unittest discover -s timescaledb-init/tests -p test_run_migrations.py -v`.
The tests own and remove fresh databases. They verify invalid inventories and
ledger history return nonzero before any pending statement commits, immutable
loaded content under changing deployment files, and shipped recovery migration
replay preserving pending work. Without the container variable they explicitly
skip; that is not real storage evidence.
