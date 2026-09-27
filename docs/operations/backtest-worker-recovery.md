# Backtest worker upgrade and recovery

The worker executes one standalone Backtest Run at a time. The database execution
slot is held from the queued-to-running claim through confirmed child and
descendant exit, reaping, and committed terminal storage. The slot does not
expire automatically. A held or faulted slot is an operational stop, not
permission to start another worker or rewrite history.

## Execution environment

Run the asynchronous worker on Linux (including the supplied Compose service).
Each request uses a dedicated child-subreaper supervisor and a separate strategy
process. Session changes and double-forks do not escape adoption. After the
strategy process exits, the supervisor stops remaining descendants and uses
`waitpid` to reap them before reporting completion; the worker then reaps the
supervisor. These cleanup deadlines apply only after execution has ended and do
not impose a normal run timeout.

Linux child-subreaper support and readable `/proc/self/task/*/children` are
required. Native macOS/Windows asynchronous workers fail closed; run them through
Compose. If supervision is unavailable, the supervisor dies, descendant signaling
is denied, or exit cannot be proved, `child_exit_unconfirmed` retains the slot.
Stopping just the original process group is insufficient: detached descendants
may still be running. For Compose recovery, stop every worker container and
verify its process namespace has exited before clearing the slot. For a native
Linux worker, verify the entire supervisor/strategy tree, including detached
sessions, or keep the slot held.

## Upgrade with queued or running work

1. Stop every old backtester worker instance before applying `V009` or starting
   the new worker. Verify its child processes and descendants have exited. Stop
   the old API before swapping accessor code so no legacy lifecycle writer can
   race the migration.
2. Run `make migrate-db` against the existing database, then deploy the new
   database accessor API, shared client, and backtester worker. Do not delete
   `backtest_runs`, Fills, Closed Trades, or queued requests.
3. Start one new worker. With the slot free, startup reconciliation marks any
   interrupted `running` runs `failed` with `worker_interrupted` once. It leaves
   `queued` runs unchanged, then resumes FIFO claims. Confirm these states via
   the public `GET /backtests` and Workspace refresh.

## Recover a held or faulted slot

1. Stop **all** backtester worker instances. Verify the recorded run's child and
   descendants have exited or terminate them and verify exit. Do not clear a
   slot based on elapsed time or heartbeat staleness alone.
2. Inspect `SELECT * FROM backtest_execution_slot;` and the referenced
   `backtest_runs` row. Record the run ID, owner token, and any fault code in the
   incident log. If process exit cannot be confirmed, keep the slot held and
   investigate; no new claim is safe.
3. After exit is confirmed, clear the single slot in one transaction:

   ```sql
   BEGIN;
   SELECT * FROM backtest_execution_slot WHERE slot_id = 1 FOR UPDATE;
   UPDATE backtest_execution_slot
      SET owner_token = NULL, run_id = NULL, fault_code = NULL,
          fault_message = NULL, updated_at = now()
    WHERE slot_id = 1;
   COMMIT;
   ```

4. Start one worker. Its first storage transaction reconciles interrupted
   `running` rows to `failed` with `worker_interrupted`; repeated restarts do not
   alter terminal rows. Confirm the former running run is failed, queued runs
   remain queued, and the next eligible run can claim. The accessor rejects a
   late write with the old owner token and any legacy tokenless lifecycle write,
   including one received between slot clear and reconciliation.

If reconciliation fails, stop the worker and preserve the slot state and error
for diagnosis. Never force a `running` row back to `queued`: execution is not
retried automatically. Existing successful history and artifacts remain intact.
