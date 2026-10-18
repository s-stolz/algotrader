# Backtest Workspace review and corrections

Reviewed on 2026-09-27 against `.scratch/backtest-workspace/spec.md`, implementation
series `e90896f...21ef19d`, and the user's request for separate history and analysis
pages, Naive UI calendars, clearer tables, and stable polling.

## Spec

All six concrete findings from the independent Spec review were corrected:

1. **Cancellation after a child result:** the supervisor stopped checking
   cancellation while waiting for the result-producing process to exit. It now
   continues supervision until exit is confirmed. Covered by a regression for
   cancellation during shutdown and the Linux process supervision suite.
2. **Batch execution logs closed on polling:** member logs were reconciled against
   standalone-only history. They now follow the selected batch's members.
3. **Execution-log filters reset on polling:** equivalent run objects retriggered
   a watcher returning a new array. Independent primitive watch sources preserve
   the active tab and filters.
4. **Unrelated batch progress erased selected curves:** successful replay data is
   retained when another member changes. Explicit refresh preserves visible
   curves while reading; Lightweight Charts instances and viewport survive data
   updates.
5. **First-start timestamp missing after pause/resume:** first member claim now
   records actual start time and the started event even when an unstarted batch
   was resumed into the running control state. Verified with PostgreSQL.
6. **Queue snapshots mixed lifecycle states:** queue reads now share the execution
   slot lock while projecting active ownership and waiting turns. A concurrent
   PostgreSQL settlement regression proves the read cannot see an active batch
   and its newly queued turn simultaneously.

Additional corrections found during diagnosis:

- Background detail reads no longer insert loading text on every poll.
- Slow queue, batch, and selected-run reads can finish instead of being
  superseded by each automatic polling tick. Batch polling stops on deactivation.
- Interrupted replay loads resume on workspace activation.
- Batch read failures are visible even before any batch detail has loaded.
- Drawdown sorts by the positive loss magnitude displayed in the table.
- Missing stored candles produce `historical_data_unavailable` with an actionable
  message. Unexpected errors retain sanitized generic messages.

The requested UI now has distinct history and current-backtest analysis surfaces
in the existing memory router. History filters and pagination survive navigation;
analysis retains its unified comparison table and stacked full-width charts.
Creation calendars use Naive UI and explicit UTC date conversion. Tables have
readable widths, pinned identity/actions, compact controls, consistent typography,
and clearer numerical presentation. Queue telemetry is a compact expandable panel.

## Standards

The independent Standards review identified two documented concerns and two
judgment calls:

- **Timestamp transport — corrected.** Public lifecycle events now expose
  `occurred_at_ms` without leaking the storage-only ISO `occurred_at` field,
  matching the root context's epoch-millisecond transport rule.
- **Workspace responsibility size — remains a maintenance concern.** The view
  still coordinates history, selection, commands, and analysis. Separate user
  pages were implemented without a broad structural rewrite. Existing file-size
  lint warnings remain nonblocking; future decomposition should isolate analysis
  ownership while retaining the polling regressions.
- **Possible Feature Envy — nonblocking judgment.** The public member route uses
  the existing persistence mapper to turn stored records into public records.
- **Primitive Obsession — nonblocking judgment.** Batch application projections
  still use dictionaries. Typed projections would improve future maintenance;
  there is no demonstrated behavior defect from this alone.

## Verification

- Frontend gate: 53 test files, 246 tests passed; ESLint, TypeScript, test layout,
  and production build passed. Existing file-size and bundle-size warnings remain.
- Full backtester suite: 292 tests passed in a disposable Linux Compose container,
  including process supervision tests. The frontend queue fixture was mounted
  read-only for its shared contract test. The entrypoint test now checks public
  OpenAPI paths rather than version-dependent FastAPI router internals.
- Accessor suite: 93 tests run, with 67 passed and 26 opt-in tests skipped. Separately, all 13
  live PostgreSQL batch tests passed using isolated temporary schemas, including
  the new first-start and concurrent snapshot regressions.
- Python lint/format checks and all configured Pyright targets passed.
- Browser checks exercised history/analysis navigation, the Naive calendar,
  successful exact replay, and execution-log records.
- Final visual polish passed the workspace, chart, and execution-log tests,
  focused ESLint, TypeScript, and a fresh production build.
- Local backend services were reloaded after confirming an idle, empty queue.

The pre-existing EURUSD run failed because its requested date range had no stored
candles. Its immutable failure history was preserved. A new offline verification
run, **Workspace verification · BTCUSD**
(`1d1e0d41-db03-45e6-83d0-44a8db8ab2df`), succeeded using stored July 23 candles:
62 closed trades, 63 fills, and exact equity replay. It remains in history for
inspection. No new market data was fabricated or backfilled.

Review totals: six Spec findings fixed; four Standards findings, with the timestamp
violation fixed and three maintenance concerns recorded. The worst Spec issue was
uncancellable shutdown; the main remaining Standards concern is view responsibility
size. The review does not certify every possible production interleaving or data set.
