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

## Durable live write guards

A **live write guard** preserves the pre-batch confirmed boundary while an M1 live
batch can partially commit or lose its write receipt. It exists per logical
Market/account source only while a batch is unconfirmed; it is neither a historical
completeness index nor a reason to download history during normal successful live
traffic. V019 adds `live_write_guards` without changing existing Candles or pending
work; V001–V018 remain immutable.

- `GET /recoveries/live-writes/{symbol_id}?account_id=...` returns `{guard: record | null}`.
- `POST /recoveries/live-writes/begin` accepts source and nonnegative `boundary_ms`.
  Commit the returned guard before any live chunk can be written. The atomic
  upsert preserves the least existing boundary and replaces opaque `write_id`.
- `POST /recoveries/live-writes/finish` accepts source and `write_id`, returning
  `{updated: bool}`. Conditional deletion cannot remove a newer attempt's guard.

Ingestion installs a guard under the Market protection lock before the first
chunk of each live callback. It retires the guard only after every chunk has a
confirmed write response. Failed or uncertain Candle writes, shutdown, and failed
subsequent boundary saves leave that old boundary durable. A failed guard begin
never permits Candle writes. A lost guard-finish response is safe: every Candle
write was already confirmed; any remaining guard can be recovered or replayed.

Startup loads pending work and the guard before looking up latest or applying a
fresh lookback. A surviving guard is merged into pending recovery with its original
boundary, even if a partial/uncertain batch moved latest or the lookback shortened.
Only after the pending save succeeds can that guard be retired. Failure between
those operations leaves at least the guard or pending work durable. The same
promotion applies to dependency recovery in a surviving process. Every later live
attempt installs a new guard before writing, so a completed historical operation
cannot expose an unguarded retry. Ordinary confirmed callbacks retire their own
guard without advancing historical recovery or requesting more history.

## Protected startup and handoff

Initial Redis connectivity and Market enumeration retry dependency failures with
capped backoff before starting any Market consumers. These initialization tasks
are owned and drained during shutdown. Each Market then starts independently.
Before selecting a new latest-Candle boundary,
load existing pending work and any live write guard. Their earliest boundary is
authoritative even if a newer live row exists or a rolling lookback has advanced.
With neither pending work nor a guard, use the
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
change is discarded; subsequent history recovers it. The stream registry stamps each Candle's transport session before queueing it.
The single FIFO writer assigns a random publication identity for that queued
session and the stream's current loss revision. Already queued old transport
sessions stay ordered before newer ones, rather than borrowing the latest
transport identity. Queue overflow increments a loss revision outside the lossy
queue. Before the next publication attempt starts, the writer observes that
revision and changes publication identity, even for previously queued Candles.
An already in-flight XADD precedes that change in publication order. Failed or
uncertain XADD increments the same revision and retries the retained Candle
indefinitely with exponential backoff capped at 30 seconds; subsequent queued
Candles share the changed identity until another interruption. Repeated overflow
or publication failure cannot remove the pending loss signal. Other streams have
independent writers; stopping a stream cancels and awaits publication retries.
Elapsed time, missing Candles, weekends and holidays do not change identity.

The broker resets its transport after 60 seconds without an incoming protocol
message. Heartbeats count as protocol traffic; missing Market data does not.
The watchdog runs on the transport reactor, is cancelled on disconnect, and lets
the SDK reconnect through the normal authentication and restoration callbacks.

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

## Dependency interruptions

An ingestion XREAD error or live persistence failure requests the same durable
recovery operation even when the producer continuity is unchanged. Before another
read or replay of the fetched batch, close the affected Market's write gate,
load/merge pending work and successfully save it. Failed pending/latest lookups
are failures, never empty history. Failed saves leave the trigger pending and the
gate closed. Consumer retries use the configured initial and maximum recovery
backoff, doubling indefinitely to the cap and resetting after successful work.

Keep the unacknowledged batch, cursor and withheld open Candle through retry.
Only advance a session run's cursor after its protection and whole write callback
succeed. The service retains the boundary from startup or the last fully confirmed
live batch and durably guards it before writing any live chunk. A failed
multi-chunk write uses that old boundary, even if an earlier
chunk committed and moved the latest database row. The retry durably merges that
boundary before replaying any failed batch; existing earlier pending work wins.
A new handoff covers the interruption's open minute once closed data resumes.
Historical failures already have a durable pending window: retrieval, write or
progress failure keeps that window pending and safely replays it. An overlapping
interruption increments its revision, so older completion cannot clear it.

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

`services.ingestion_service.history.lookback_days` or quoted UTC `services.ingestion_service.history.start_date` selects the fresh
history boundary. Set the unused value to null, regenerate config, and restart
ingestion. The default remains 90 days; a changed policy does not
clip accepted pending work. Expanding the policy does not audit older history
before an existing Market's latest Candle.

The existing ledgered V001–V017 migrations and their checksums remain unchanged.
`timescaledb-init/migrations/V018__pending_recovery.sql` adds pending state and
`V019__live_write_guards.sql` adds pre-write crash protection without changing
existing Candles or backtest contracts. Apply both before starting the compatible
accessor/ingestion. The existing `scripts/migrate_db.py` runner records versions,
names and SHA-256 checksums under a session advisory lock in `schema_migrations`.
Fresh volumes use `01-run-migrations.sh`; existing volumes use `make migrate-db`.
Replay skips identical migrations; missing/renamed files, duplicate versions,
gaps and checksum drift fail before pending SQL. Applied SQL is immutable;
later changes require a new forward migration. See the
[Timescale context](../../timescaledb-init/CONTEXT.md) for legacy baselining.

For existing volumes:

1. Stop ingestion before changing its storage or continuity contract. Preserve
   Redis streams and all pending rows; do not drain or delete real history.
2. Build/deploy the self-contained Timescale image, then run `make migrate-db`.
   Use the configured database and preserve its migration ledger. For queued or
   running backtests, follow the [worker cutover](../operations/backtest-worker-recovery.md#upgrade-with-queued-or-running-work).
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

For the one-command disposable stack check and release procedure, read the
[deployment and acceptance guide](../operations/market-data-recovery.md).

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
Seven additional runtime phases keep broker connectivity healthy: Redis read,
database latest-read and live-write failures, plus actual broker registry queue
overflow and failed Redis publication. The two restart-before-save phases commit
a live prefix or lose a normal-size committed write receipt, fail the subsequent
boundary save, and kill ingestion before that save can recover. Restart with a
one-day lookback must recover the supplied October 6 history from the durable
guard. The producer phases run a separate
controlled broker publisher with one unchanged source connection and real Redis.
The consumer read fault is a controlled Redis adapter; database faults are HTTP
503 responses at the real accessor client boundary. Every runtime phase completes
startup first, preserves the old boundary durably before resumed live writes,
kills ingestion, restarts with a shorter lookback, verifies the supplied October 6
and October 18 historical values in Timescale, and verifies further live writes.
Each phase verifies persisted Candles and pending state, without expecting one
Candle per calendar minute. It removes only its synthetic Market and stream.
No process or storage test may target real history. Missing environment variables
produce explicit skips, never evidence of acceptance.

For live migration acceptance, start an owned disposable Timescale container
named `vibe10r1-*`, set `RECOVERY_MIGRATION_TEST_CONTAINER` to that name and
`RECOVERY_MIGRATION_TEST_USER` to its synthetic PostgreSQL user, then run
`python -m unittest discover -s timescaledb-init/tests -p test_run_migrations.py -v`.
The tests own and remove fresh databases. They verify fresh full-inventory replay,
V017-to-V019 upgrades preserving applied checksums and named experiments, pending
V018 work surviving the guard upgrade, and replay preserving recovery rows.
Without the container variable they explicitly skip; that is not real storage
evidence.

For separate migration-runner unit coverage, run
`python -m unittest scripts.tests.test_migrate_db -v`. These checks cover migration
inventory and checksum validation, ledger validation before pending SQL, and
execution of the same loaded SQL content used for checksums.
