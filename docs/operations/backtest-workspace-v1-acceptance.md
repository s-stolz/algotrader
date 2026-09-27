# Backtest Workspace v1 acceptance

The integrated Workspace was accepted on 2026-09-27 against a rebuilt local
Compose stack and a separate representative upgraded database. The stack used
synthetic Candle rows in TimescaleDB; all runs, results, queue turns, worker
heartbeats, and browser views came from real storage and production API routes.
No production route used a prototype fixture or simulated run outcome.

## Reproduce the gates

Use the commands in `docs/agent/COMMANDS.md` from the repository root. Generate
configuration from a local secret input, build the full stack, and run:

```sh
make up-build
make migrate-db
make smoke-backtester
make test
make test db_accessor_client
make test frontend
./lint-python.sh
make typecheck-python
RUN_MIGRATION_INTEGRATION_TESTS=1 .venv/bin/python -m unittest scripts.tests.test_migrations_integration
make verify
```

For the opt-in accessor execution, batch, and deletion Postgres suites, point
`BACKTEST_BATCH_TEST_DATABASE_URL` to a disposable local Timescale database,
set `BACKTEST_INTEGRATION_ENV_DIR` to generated local configuration with its
published Timescale port, set `BACKTESTER_TEST_PYTHON` to the backtester virtual
environment interpreter, set `PYTHONPATH` to the accessor directory, and run
from `database-accessor-api/`:

```sh
RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS=1 \
  .venv/bin/python -m unittest discover -s tests -p 'test_backtest*postgres.py'
```

The acceptance run used an isolated Compose project with alternate localhost
ports and a fresh volume. Its main database applied migrations V001–V016 in
order. The migration integration suite passed 14 tests; the opt-in real Postgres
suite passed 24. The full verification gate passed every configured backend,
Python lint/typecheck, and frontend gate (53 spec files, 237 tests and build).
The deployed smoke passed one successful run with persisted Fills and Closed
Trades and one failed missing-market run without result artifacts. `make
migrate-db` subsequently reported the ledger already up to date.

For an isolated project with alternate published ports, pass both public URLs
explicitly to the host-side smoke runner. The acceptance run used:

```sh
backtester/.venv/bin/python backtester/smoke.py \
  --backtester-url http://127.0.0.1:62020 \
  --storage-url http://127.0.0.1:62000
```

## Integrated flow evidence

| Delivery milestone | Observed result on the rebuilt stack |
| --- | --- |
| Standalone | `7768b18a-7a66-4295-949f-8abb0c196e16` succeeded and retained 15 Fills, 14 Closed Trades, saved metrics, and 1,380 exact Equity Replay points. The last exact equity was 10042.91864488177; exact max drawdown matched saved `max_drawdown_pct` -0.005885630440850245. A separate missing-Candle run failed without artifacts. |
| Sweep and fair execution | Batch `00e8601a-d652-4e4e-83e9-26f53e36516b` settled four fixed members: two succeeded and two failed. A standalone turn started between batch members 1 and 2. Failed members did not remove prior successful results. |
| Controls and operations | A long-running child retained a fresh heartbeat. Pause drained the active member and held the next member queued; Resume placed the batch after an earlier standalone turn. Queued individual cancellation settled immediately. Active individual and whole-batch cancellations passed through `cancelling`, retained the slot until exit, and preserved previous successes. |
| Analysis and reuse | The deployed browser selected two real successful members and rendered two exact equity/drawdown curves. `Run settings` and a custom Ending equity column worked with horizontal table scrolling. The execution-log drawer displayed Closed Trades and Fills while both comparison selections remained checked. Chart handoff showed the run overlay and return restored the selected Workspace context. Create from this made independent standalone run `9850b3fc-2404-485f-9473-e919e41135c5` and independent four-member batch `7bfb02db-4d7e-42f0-bcfc-64406e46285e`; the source records remained. |

The browser's mixed-batch table showed exact ending equities
10019.967981897826 and 10018.814353674084, distinct from Initial capital
10000 and saved Return. A separate two-market successful batch
`63316b5e-3aa5-4d50-aa04-0325e452903a` showed the note “Compared runs differ
in Market” and exact ending equities 10019.967981897826 and
10027.870584725728. The UI disabled comparison of failed members. A saved
version-2 success displayed its metrics, “Version unavailable,” an explicit
unavailable replay reason, and a disabled chart handoff. Create from this
required `Use current version`, displayed saved-versus-current parameter
changes, then created independent version-3 run
`fe14114f-2ebd-4dfc-8cf5-8c1856233646` after current validation.

Public deletion rejected a direct batch member, a queued standalone, and a
paused batch with HTTP 409. Terminal standalone deletion returned 204 and its
detail, Fills, Closed Trades, and replay reads returned 404. Whole-batch
deletion returned 204; its four members returned 404 and direct database checks
found zero remaining member runs, Fills, or Closed Trades. An unrelated batch
remained inspectable.

## Upgrade and cutover evidence

The upgrade rehearsal staged migrations V001–V006 in a separate database, then
inserted normalized version-2 standalone request snapshots: a successful run
with result metrics, diagnostics, two Fills and one Closed Trade; a queued run;
and a running run. The forward-only runner applied V007–V016 and recorded every
version exactly once. It preserved all three run identities, the successful
result and artifacts, and the queued turn. No batch membership or Equity Replay
descriptor was manufactured. Public history, detail, Fills, and Closed Trades
remained HTTP 200. The old success returned `replay_metadata_missing` from the
equity route. A legacy response defect exposed by this rehearsal was fixed:
version-2 requests now omit an absent `strategy_version` instead of serializing
it as `null`.

Starting one new worker against the upgraded database reconciled the old
running row once to `failed/worker_interrupted`. It consumed the durable queued
turn and failed it closed with `strategy_version_unavailable`, because the old
request has no exact Strategy Version. The earlier successful row stayed
`succeeded` with artifacts intact. This tests the upgrade ordering in
`docs/operations/backtest-worker-recovery.md`: stop old writers and confirm
their child/descendant exit; apply schema before new accessor/client/worker
code; start one new worker after the slot is free. The upgrade requires neither
history deletion nor a full queue drain.

The rebuilt stack also exercised a killed active worker. A second worker could
not claim while the first owned the slot. After the first container and its
process namespace exited (`false 0`), the public queue became `stale` and its
health probe returned 503. Stopping the accessor made the queue read 503
`unknown`, never an empty queue. The operator then inspected and cleared the
held slot in the serialized transaction documented in the recovery guide. One
new worker failed the interrupted run once, executed its previously queued
standalone turn, and left a paused batch paused. In a separate kill during
accepted individual cancellation, the slot remained held and the run remained
`cancelling` until the same verified-exit recovery; startup reconciliation
settled it `cancelled` without Fills or Closed Trades and ran the queued turn.

An owned `terminal_persistence_failed` fault was injected through the
accessor's operational fault endpoint while a real child was paused. The public
queue reported `faulted`, the health probe returned 503, and the active slot
and queued turn remained. Recovery began only after the worker process namespace
was confirmed exited. Existing worker tests additionally cover actual
settlement failure and unconfirmed child/descendant cleanup; the injection
proves deployed fault visibility and capacity retention, not an actual disk
failure. The recovery guide is the operator procedure for both cases.

The root and backtester, accessor, frontend, shared-client, and Timescale
contexts match these contracts; `docs/agent/CONTRACT-CHANGES.md` names their
producers, consumers, and checks. ADR-0005 retains backtester policy ownership;
ADR-0006 retains forward-only checksum-ledgered migration discipline. Neither
decision needs revision for this acceptance work.
