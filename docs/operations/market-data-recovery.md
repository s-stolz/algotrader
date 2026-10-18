# Market data recovery deployment and acceptance

Recovery retrieves broker-available closed M1 Candles after known interruptions.
It does not infer gaps from calendar minutes. A fresh Redis Candle or a healthy
container proves neither historical completion nor durable progress. The
[recovery contract](../contracts/recovery.md) owns continuity, startup ordering,
pending revisions, and live write guards; [Candle persistence](../contracts/candles.md)
owns historical corrections and aggregate behavior.

## Run the controlled smoke check

Use Python 3.12+, Docker with a running daemon, and a **combined** Python environment
containing ingestion, accessor, broker, and backtester dependencies. Child processes use that
same interpreter; setting only a parent's `PYTHONPATH` to another environment's
packages is insufficient. From this checkout, one possible setup is:

```sh
python3.12 -m venv /tmp/algotrader-recovery-env
cd ingestion-service
/tmp/algotrader-recovery-env/bin/pip install -r requirements.txt
cd ../database-accessor-api
/tmp/algotrader-recovery-env/bin/pip install -r requirements.txt
cd ../broker-service
/tmp/algotrader-recovery-env/bin/pip install -r requirements.txt
cd ../backtester
/tmp/algotrader-recovery-env/bin/pip install -r requirements.txt
cd ..
make smoke-recovery PYTHON=/tmp/algotrader-recovery-env/bin/python
```

The [runner](../../scripts/smoke_recovery.py) never reads local secrets or uses
Compose. It creates uniquely named disposable Timescale and Redis containers with
random loopback ports and synthetic credentials. It starts the accessor from this
checkout and controlled upstream HTTP fixtures, exercises real ingestion child
processes, then removes its own containers and anonymous volumes. Existing stack
services, Redis streams, Bitcoin history, and other real Markets are untouched.

For a named evidence directory or an image pinned by digest:

```sh
/tmp/algotrader-recovery-env/bin/python scripts/smoke_recovery.py \
  --output /tmp/recovery-acceptance-unique \
  --timescale-image timescale/timescaledb:latest-pg17 \
  --redis-image redis:7-alpine
```

Use `--backtester-python /path/to/backtester/python` when backtester dependencies
are installed in a separate environment.

The output directory must not exist. Preserve its `report.json`, per-check logs,
full Docker inspection/image identities, and the checkout's exact Git SHA/diff.
The default image tags follow this repository's stack; pin digests when comparing
releases. A nonzero exit or skipped required scenario fails the smoke check.
The runner reports cleanup failures. After a forced termination of the runner,
use its recorded container IDs to inspect and remove only those owned fixtures;
never use `docker compose down -v` or a blanket prune as test cleanup.

The smoke check runs these existing behavioral seams together:

- Eleven real process phases in
  [test_recovery_process.py](../../ingestion-service/tests/test_recovery_process.py):
  before boundary save, protected live write, after historical writes before
  progress, rapid session changes, Redis read failure, database read/write failure,
  publication loss, queue overflow, lost live receipt before failed boundary save,
  and partial live commit before failed boundary save. It seeds October 5 history,
  resumes October 18 live data, kills ingestion with work pending, shortens the
  restart lookback, then verifies supplied historical values, pending completion,
  and further persisted live delivery. No assertion assumes one bar per minute.
- Real historical ingestion HTTP checks for authoritative overlap correction,
  uncertain committed chunks, and incomplete download rejection.
- Ingestion service scenarios for silent weekends without a new trigger,
  completed empty intervals, repeated interruptions, and independent Markets.
- Real accessor/Timescale tests for conditional completion races, durable guards,
  compressed historical correction, duplicate-safe replay, concurrent live writes,
  and refreshed higher-Timeframe values.
- The shipped forward migration runner, initial application and unchanged replay,
  plus its real database tests for immutable inventory, drift/gap rejection, and
  V017-to-V019 upgrade preserving pending work and guards.

The upstream is deterministic; this check does not authenticate a real cTrader
session or deploy the production stack. Source callback/transport tests complement
it as described below.

## Coverage and release evidence

| Failure or contract | Verification seam and expected outcome |
| --- | --- |
| Quick reconnect missed by health polling; broker restart | Broker `tests/infrastructure/test_ctrader_client.py` and `test_live_continuity.py`; ingestion process `sessions` phase keeps health up while identities change, retains the earliest work and recovers after restart |
| Old queued data; mixed session batches | Broker continuity tests preserve FIFO/session association; ingestion `test_recovery.py` verifies ordered contiguous runs, rejected untrusted rows and failed-run replay |
| Failed publication; queue overflow | Process `publication-loss` and `queue-overflow` use the real broker registry publisher and Redis while connection health remains up; recovered fixture Candles are read from Timescale |
| Redis read, latest lookup, recovery save, live persistence failure | Process fault phases and ingestion service tests keep writes gated until durable protection, retain batches and let other Markets progress |
| Partial download / pagination / empty response | Broker `tests/api/routers/test_market_data.py` drives the actual ingestion BrokerClient parser through pagination, empty, and interrupted responses; historical integration rejects partial streams; successful zero-result intervals finish |
| Partial / uncertain live write and failed subsequent boundary save | Two process restart-before-save phases read the durable guard after kill; shorter lookback cannot erase October 6 fixture history |
| Historical write committed but receipt lost | `test_history_integration.py` replays the original window and verifies exact unique OHLCV through HTTP; storage tests prove idempotence |
| New interruption during recovery; stale progress | Process sessions plus real `test_recovery_postgres.py` races reject old identity/revision/cursor and retain newer pending work |
| Overlap correction, compressed chunks, live/history races | Real `test_historical_candles_postgres.py` validates authoritative values, omission preservation, stale live protection and explicit aggregate refresh |
| Silent / closed market | `test_silent_weekend_does_not_change_session_or_schedule_more_history` asserts no new history request; `test_failed_market_releases_global_capacity_and_empty_history_completes` accepts supplied empty completion |
| Metadata consumers | Webserver `tests/test_redis_consumer.py` and Indicator `tests/services/test_live_indicator_manager.py` consume legacy/valid/invalid metadata while preserving public Candle output |

Run the repository's full gate and suites from this checkout and retain their
actual results, including skipped tests:

```sh
make verify
make typecheck-python
./lint-python.sh
make test
```

Some repository revisions lack the first two targets; a missing target is an
unavailable gate, never a pass. Use the release's explicitly approved baseline
exception if one exists, with affected-code lint/types and no-new-failure evidence.
`make test` covers only the suites listed in the Makefile. Also run the accessor,
shared client, broker infrastructure/API, webserver, Indicator service,
configuration, and migration suites using their service environments. Webserver
and Indicator parsing compatibility are not established by engine tests alone.

The smoke command enables `HISTORY_TEST_DATABASE_URL`, `HISTORY_TEST_ACCESSOR_URL`,
`RECOVERY_TEST_ACCESSOR_URL`, `RECOVERY_TEST_REDIS_URL`, and
`RECOVERY_MIGRATION_TEST_CONTAINER` against its own fixtures. Without those opt-ins,
ordinary suites explicitly skip storage/process/migration evidence; list such skips
as unverified. The real storage checks require TimescaleDB 2.11+ / PostgreSQL 14+
for compressed-chunk DML. Record actual versions and image IDs from each run.

Before release, record the final relevant SHA, input/configuration identity,
commands, results, skip counts, and outstanding manual/environment checks. If code
or deployment configuration changes, rerun the affected evidence. Remaining
qualification needs an exact procedure and result, not a statement of container
health. An operator may validate a real broker on a separately authorized synthetic
account/Market: establish a stored boundary, interrupt that isolated source,
observe pending before new writes, restart ingestion while pending, then compare
persisted OHLCV with all supplied broker results and verify subsequent live writes.
Do not induce failures in a production broker session for acceptance.

## Upgrade an existing volume

1. Record release/image/configuration identities and the configured database,
   account, and Market identities. Take the usual database backup. Stop ingestion
   **before** replacing its persistence or continuity dependencies:
   `docker compose --env-file config/.env.shared stop ingestion-service`.
   Keep ingestion stopped throughout steps 2–4.
2. Build this release's self-contained Timescale image and apply its forward
   migrations to the configured database with `make migrate-db`, following the
   [worker cutover](backtest-worker-recovery.md#upgrade-with-queued-or-running-work)
   when backtest work is queued or running. The existing Python runner and
   `schema_migrations(version, name, checksum_sha256, applied_at)` ledger remain
   authoritative. V001–V017 are unchanged; V018 creates pending recovery and V019
   creates live write guards. Verify all nineteen ledger entries and unchanged
   replay. Preserve applied checksums, existing history and recovery rows; never
   drop or rewrite the ledger to force success.
3. Build/deploy the compatible accessor and shared clients, then webserver and
   Indicator consumers. Example:
   `docker compose --env-file config/.env.shared up -d --build database-accessor-api webserver indicator-api`.
   These consumers preserve the existing public Candle/WebSocket fields while
   accepting the additional Redis metadata. Verify dependency responses; a health
   endpoint alone does not exercise pending-recovery transactions.
4. Build/restart the compatible broker:
   `docker compose --env-file config/.env.shared up -d --build broker-service`.
   A new producer identity distinguishes process restart. Historical producer and
   ingestion client must both support explicit completion. Keep stable stream
   names. Retain legacy Redis entries: startup snapshots the tail and retrieves
   history from the database boundary through subscription setup. Legacy/invalid
   rows after that tail request recovery and are discarded from live persistence;
   they cannot silently enter storage as protected modern data. No stream flush,
   history deletion, or Bitcoin repair is a rollout step.
5. Resolve history configuration through `config/topology.yaml` plus local
   overrides, then `make validate-config` and `make config`. Start compatible
   ingestion with `docker compose --env-file config/.env.shared up -d --build ingestion-service`.
   It must load existing pending work and guards before considering latest history,
   durably protect the boundary before live writes, and replay unfinished windows.
   Recheck persisted historical values and pending state as below.

## Configuration, observation, restart, and rollback

Tracked history selection is exactly one of `services.ingestion_service.history.lookback_days` (default
90) or quoted UTC `services.ingestion_service.history.start_date`, such as `"2026-10-05"`, with the other
set to null. Generated names are `INGESTION_HISTORY_LOOKBACK_DAYS` and `INGESTION_HISTORY_START_DATE`.
The boundary is resolved once per ingestion instance. Empty Markets start there
inclusively; populated Markets include the last stored M1 within the boundary.
Changing this policy neither deletes data nor scans older history. Existing
pending work and live guards retain their earlier boundary across a rolling or
shorter lookback.

The ingestion [configuration owner](../../ingestion-service/app/config.py) also
supports these direct runtime variables; they are not topology keys generated by
the current configuration schema. Supply explicit environment values through a
Compose override when tuning; do not edit generated files and expect regeneration
to preserve them. Use positive integers and a maximum backoff at least the initial
value.

| Runtime setting | Default | Purpose |
| --- | --- | --- |
| `STARTUP_WATERMARK_CONCURRENCY` | 2 | Concurrent initial boundary reads |
| `STARTUP_STREAM_START_CONCURRENCY` | 8 | Concurrent Market startup/subscription protection |
| `STARTUP_BACKFILL_CONCURRENCY` | 4 | Concurrent finite history windows across Markets |
| `RECOVERY_BACKOFF_INITIAL_SECONDS` | 5 | First retry delay |
| `RECOVERY_BACKOFF_MAX_SECONDS` | 300 | Capped indefinite recovery retry delay |
| `BROKER_HEALTH_POLL_SECONDS` | 10 | Supplementary connectivity observations; continuity metadata catches brief losses |

Recovery is serialized per Market and uses finite one-day windows. Failures retry
indefinitely; a failing Market releases global history capacity during backoff.
The broker separately retries failed publication with a 30-second cap. Silence
alone changes neither continuity nor recovery state.

Inspect ingestion logs with
`docker compose --env-file config/.env.shared logs --since 15m ingestion-service`.
Look for `Recovery protected` (Market/account/M1 interval, trigger, revision),
`Recovering`, `Recovery window complete`, and `Recovery failed ... retry=...`.
Initialization failures say `Recovery startup protected`. One completed window
is not whole-source completion: confirm all saved windows progressed and
`GET /recoveries/{symbol_id}?account_id=...` successfully returns `pending: null`.
A failed lookup is not null. Observe the guard endpoint as well; transient guards
are normal for active batches, while a surviving guard denotes unconfirmed work.
Use completed download records and persisted broker-supplied OHLCV to establish
success, then verify later closed live Candles are persisted.

For a planned ingestion restart, send SIGTERM through Compose and wait for shutdown;
active writes/tasks drain and pending/guards remain durable. Abrupt crashes are
safe to replay: confirmed history writes before progress may repeat; lost live
receipts retain the pre-batch boundary. Do not manually clear pending/guard records,
advance cursors, delete a Market, change account/Market identity, or reset volumes
to make recovery appear finished. Deleting a Market cascades its pending state.

For rollback, stop ingestion first and retain the database, streams, pending work,
guards, and migration ledger. Run a compatible recovery-aware ingestion release,
or keep it stopped until a forward fix is available. An older consumer ignores
the write gate and cannot safely resume this state. Do not reverse V018/V019 or
restore an older database snapshot over newer accepted work as a routine rollback.
After a compatible restart, confirm the same earliest unfinished interval and
compare eventual stored results; newer live data must not replace the boundary.

Historical writes correct only supplied closed M1 values; omitted timestamps and
unrelated history remain. Higher-Timeframe materializations follow existing
refresh policies. For corrections outside a policy's rolling window, schedule an
explicit `refresh_continuous_aggregate` for the affected view and bucket-aligned
interval after verifying that view's definition. No automatic refresh of old
materializations is promised by recovery. Users manually reload charts to load
recovered history; existing live Indicator state is not automatically rebuilt.
No recovery UI, Backtester restriction, timestamp-density scanner, or synthetic
Candle generation is introduced.
