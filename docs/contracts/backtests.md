# Backtest Contracts

Read for Backtest creation, lifecycle, copying, storage, or Equity Replay changes.
Backtester owns domain policy and the public API; the accessor owns atomic
storage, and shared clients pass documents through.

## Backtests and Runs

A **Backtest** is an immutable definition and its nonempty collection of **Runs**.
A Run executes one resolved combination of Market, Timeframe, Strategy Version,
parameters, and Allowed Directions. Every Run belongs to exactly one Backtest and
has a contiguous zero-based `run_ordinal`, displayed as `Run #N` starting at one.
Fixed inputs produce one Run through the same creation, scheduling, inspection,
comparison, and control flow as multiple combinations.

Creation selects Markets, Timeframes, Allowed Directions, optional daily schedule
alternatives, and parameter axes.
Each parameter uses a fixed value, explicit values, or a numeric range.
Preview deduplicates typed values and bounds the Cartesian product before
validation. Invalid independent values reject the definition; cross-parameter
rejections appear as excluded candidates. Candidate ordinals retain full-grid
positions; Run ordinals cover only ready candidates. Preview returns every row
and writes no history. At least one ready candidate is required for acceptance.

Acceptance revalidates against current Markets, catalog, and candidate limit.
The Backtest, all Runs, normalized definition, counts, initial event, and
**Strategy Metadata Snapshot** commit together. That snapshot preserves the
strategy identity and public parameter schema. An identical normalized definition
with the same submission ID returns the original Backtest, including its original
name; changing the definition conflicts. Rerunning uses a fresh submission ID.

## Public resources

- `POST /backtests/preview`: stateless expansion and validation.
- `POST /backtests`: accept a Backtest and return `202` with its location.
- `GET /backtests`, `GET /backtests/{backtest_id}`: history and overview.
- `GET /backtests/{backtest_id}/runs` and `/events`: ordered Runs and lifecycle.
- `POST /backtests/{backtest_id}/{pause|resume|cancel}`: durable controls.
- `PATCH /backtests/{backtest_id}/name`: name-only update.
- `DELETE /backtests/{backtest_id}`: delete an entire settled Backtest.
- `/backtests/runs/{run_id}`: individual Run read; `/cancel`, `/fills`, `/trades`,
  and `/equity-curve` expose execution controls and artifacts.

The accessor uses `/backtests` for parents and `/backtest-runs` for executions.
Run creation is part of atomic Backtest acceptance. Workspace routes identify a
Backtest; its overview, Runs table, comparison tools, and selected Run inspector
are the same for every Run count.

## Strategy identity and copying

**Strategy Version** is the positive, monotonically increasing integer paired
with a registered strategy ID. Bump it for public parameter or behavior changes.
It identifies the declared strategy contract, not the complete runtime, and does
not retain retired code for execution. Request schema v3 records this identity
and fully resolved parameter values.

The **Current Strategy Catalog** comes from annotated single-file builders. Their
signatures define names, order, types, defaults, and independent constraints.
Boolean choices are inherent; explicit choices restrict other parameters.
Validation resolves the schema before applying an optional pure cross-parameter
validator, without loading Candles. Queued requests whose exact version is no
longer available fail before Candle loading with `strategy_version_unavailable`.
Already executing children retain their loaded code.

**Create from this** copies the saved configuration into an independent editable
draft. Copying a Backtest retains ordered selections, parameter modes, explicit
values, and original range bounds/steps. Saved resolved defaults become explicit
fixed values: a saved value of 20 stays 20 even if today's default is 30. Copying
a Run fixes every axis to that Run's actual values. Both retain execution settings.

The draft adopts the current Strategy Version and shows the existing version and
schema change indicators. Removed parameters are omitted; newly introduced
parameters use current defaults. Invalid retained values block preview/submission.
A fresh draft or deliberate strategy selection resets all parameter values and
modes to current defaults. Copying a Backtest preserves schedule alternatives;
copying a Run fixes the schedule to that Run's resolved triple.

## Experiment Names

A Backtest carries one nullable top-level `name`, outside its immutable definition
and Run requests. Runs use their ordinal and have no independent name. Copying a
named Backtest proposes its name plus ` (copy)`, truncating the source portion to
keep the total within 120 Unicode characters. Unnamed Backtests and copied Runs
start with an empty draft name.

Names allow duplicates. Absent, empty, or whitespace-only values normalize to
null; trim surrounding whitespace. Reject line separators in nonempty input and
names longer than 120 Unicode characters after trimming. Frontend, API, and
storage share those rules. `run_metadata.name` and `.label` are rejected;
unrelated metadata remains supported. Preview is name-free.

History displays the saved name or `Unnamed backtest`. Search uses a trimmed,
case-insensitive whole-query substring across individual names, full IDs,
submission IDs, statuses, strategy IDs, Markets, and Timeframes, combined with
filters. Naming accepts every lifecycle state and changes only `name`, preserving
requests, events, revisions, timestamps, artifacts, and queue state.

## Lifecycle and results

Backtest control states are `queued`, `running`, `pausing`, `paused`,
`cancelling`, `completed`, and `cancelled`. `running` means scheduling is enabled,
including between Runs. Outcome counts are separate: a completed Backtest can
contain failed or individually cancelled Runs. Failure does not stop other Runs.
Settled progress includes success, failure, and cancellation; executed count
includes success and failure.

- Pause blocks unstarted Runs while active work drains through `pausing` to `paused`.
- Resume retracts a pending/completed pause. Remaining work rejoins the queue tail.
- Cancel removes the turn, cancels queued Runs, and marks active work cancelling
  atomically. Prior results remain. The Backtest becomes cancelled after all Runs
  settle. Only cancelling the Backtest sets this parent state.
- Command IDs are stable across retries; receipts retain the original status and
  revision. Lifecycle revisions order durable commands and automatic transitions.
  Events record prior/new state; no-op receipts add no transition.

Run states are `queued`, `running`, `cancelling`, `succeeded`, `failed`, and
`cancelled`. Queued cancellation settles immediately. Running cancellation retains
the execution slot until verified process-tree exit and fenced settlement.
Acceptance time, source, and reason are durable; retries retain that acceptance.
Succeeded/failed Runs conflict with cancellation. Individual cancellation also
advances the parent revision and records an event.

Only successful Runs expose result artifacts. Failures expose bounded sanitized
errors; tracebacks remain in worker logs. Results use schema v3. A **Fill** is one
execution with buy/sell side. A **Closed Trade** is a completed long/short round
trip with entry, exit, realized PnL, fees, reason, and nullable planned protection
prices. Planned prices can differ from actual exits. Artifacts are ordered by
per-Run sequence. Missing Runs return not found; Runs without artifacts return
empty lists.

Deletion permits only entire settled Backtests (`completed`, `cancelled`). Storage
rechecks all Runs under the execution-slot lock and removes parent, Runs, results,
events, and command receipts atomically. Accepted requests and membership remain
immutable until whole-Backtest deletion.

## Shared execution controls

`execution.max_entries_per_day` is an optional positive integer; omitted/null
means unlimited. It counts actual entries per UTC day and Run. Booleans, fractional
values, strings, zero, and negative limits are invalid. See
[entry semantics](../../backtester/STRATEGIES.md#daily-entry-limit).

`execution.daily_schedule` is optional. Enabled schedules contain integer
`entry_start_minute_utc`, `last_entry_minute_utc`, and `exit_minute_utc`, satisfying
`0 <= entry_start < last_entry <= exit < 1440`. Each Run keeps exactly one resolved
schedule; disabled controls are omitted from its canonical snapshot.

Creation and preview may supply `daily_schedules`, a nonempty list of complete
schedule triples. Each triple is one alternative, not another session within a Run
or independently varying time fields. Triples are deduplicated in first-seen order
and expand after Allowed Directions in the Cartesian product. The candidate limit
applies before exclusions and includes this axis. Preview rows expose the resolved
`daily_schedule`, including excluded rows. Acceptance saves the normalized list
in `normalized_selections.daily_schedules`, while each Run request contains only
its resolved `execution.daily_schedule`. Definition v1 and request v3 remain
compatible: absence of the list uses the legacy shared schedule (or no schedule).
Supplying both a list and a non-null shared schedule is rejected as ambiguous.
An omitted/null list does not change legacy normalization or retry identity. See
[engine timing](../../backtester/STRATEGIES.md#daily-execution-schedule).

## Saved chart indicators

Successful runs produced by the application runner include a **Chart Indicator
Snapshot** in `diagnostics.chart_indicators`. The snapshot has `schema_version: 1`
and an ordered `items` array. Each item contains the indicator engine's stable
string `indicator_id` and its resolved `parameters`, including defaults from the
installed indicator at execution time. It describes the calculations used by the
executed strategy, not a reconstruction from the current strategy catalog.

Multiple feature outputs using the same indicator and parameters share one item;
different parameter sets remain separate. An empty array means the strategy
declared no indicator calculations. Absence means a legacy or lower-level result
has no saved chart configuration; consumers must not infer one from current code.
The snapshot is copied through worker handoff and persisted with the other result
diagnostics. It requires no separate storage migration or change to result v3.

This versions the snapshot format only. Indicator implementations are not
versioned or archived: the chart uses installed indicator code with saved
parameters. The snapshot contains no prices, decision annotations, chart styles,
or executable strategy code. Its market and timeframe come from the saved run
request; auxiliary indicator input markets remain calculation inputs.

Applying a run to the chart loads its snapshot as a run-owned indicator group,
separate from manual indicators. Calculations use the saved parameters and are
locked; styling remains editable. Changing the chart Market or Timeframe hides
the run group and trade/protective overlays without clearing run selection.
Restore returns to the saved context, reloads the group, and preserves its styles.
Overlays wait for matching Candle history before rendering. Missing installed
indicators or invalid snapshots produce a chart error rather than a guessed
configuration; legacy runs without snapshots still show their saved trades.

## Execution Slot and Queue

One durable database slot covers claim through terminal persistence. One turn
exists per eligible Backtest. A claim atomically consumes the earliest turn and
marks its lowest queued ordinal running. After settlement, remaining work joins
the tail. Outcome, artifacts, parent transition/event, next turn, and slot release
commit in one owner-token-fenced transaction.

The slot has no expiry. Release requires verified child-tree exit and reaping.
Uncertain exit or persistence failure retains capacity and exposes an operational
fault. Startup reconciles interrupted work only with a free, unfaulted slot:
running becomes failed/worker_interrupted, accepted cancellation becomes cancelled,
and queued work remains queued. See [worker recovery](../operations/backtest-worker-recovery.md).

Queue positions and heartbeat availability are advisory. Public queue entries
identify the Backtest and next ordinal; internal state also carries the next Run
ID for claiming. Active entries always include their Backtest ID and ordinal.
Claims seed an owner-matching heartbeat with database time. Periodic heartbeats
serialize with claims; delayed idle/previous-owner updates cannot overwrite the
current owner's evidence. Every claim requires a worker ID.

## Unified-model cutover

V020 deliberately discards existing Backtest history and artifacts, renames the
parent resources, and makes Run membership mandatory. There is no compatibility
API or history conversion. Stop API and workers, verify the slot is free and
unfaulted, apply migrations, then restart the matching services. The migration
refuses a held or faulted slot and leaves Markets/Candles intact. Historical
migrations remain immutable. See the [upgrade procedure](../operations/backtest-worker-recovery.md#upgrade-with-queued-or-running-work).

## Equity Replay

A **Backtest Equity Curve** is time-ordered simulated equity. Successful current
single-Market bar runs atomically store an Equity Replay descriptor alongside
metrics, diagnostics, Fills, and Closed Trades, rather than a full curve.
The **Equity Replay Fingerprint** identifies executable Candle timestamps and
closes, excluding warmup. Reads verify current Candles and replay saved ordered
Fills; they do not reevaluate strategy or indicators. Older successes retain
metrics/logs and report `replay_metadata_missing`; changed or unavailable Candles
have distinct unavailable reasons.

Descriptor v1 uses `sha256-ts-close-v1`: the domain marker
`algotrader/equity-replay/sha256-ts-close-v1` followed by NUL, length-prefixed UTF-8
exchange (empty if absent), symbol, and Timeframe, then signed big-endian int64
executable timestamps and big-endian binary64 finite closes. Negative zero is
normalized to positive zero. Fingerprint compatibility must survive code changes.

## Real-time delivery and recovery

The public API durably accepts cancellation before returning `cancelling`; worker
acknowledgment is not required for acceptance. `cancelled` still requires verified
process-tree exit and fenced terminal settlement. Queued cancellations settle
immediately. Backtest controls preserve the same atomic member/turn behavior.

The API schedules a coalesced invalidation after every mutating backtest request,
including ambiguous error responses. Publication failures retry while the process
is alive. Publisher startup republishes a reconciliation request: workers perform
the authoritative queue/active-run reads, so no API-side duplicate lifecycle
scanner is needed. Worker claims and settlement also publish invalidations.

- `backtests:control:v1`: Redis Stream entries have a JSON `payload` containing
  `{"type":"reconcile"}`. This wakes queue discovery and active cancellation
  checks. Each deployment instance uses its own stable consumer group, with the
  consumer name `worker`; group identities must never be shared by live workers.
- `backtests:events:v1`: JSON `payload` is `backtestChanged` or `backtestHealth`.
  Changes invalidate saved Workspace reads. Health carries `run_id` (nullable),
  `heartbeat_at_ms` from the persisted database heartbeat, and nullable
  `fault_code`/`fault_message`. Only matching active-run health may refresh the
  active owner's freshness; another idle worker cannot establish that evidence.
- Streams retain approximately 10,000 entries. They are delivery buffers, not
  audit records. Consumer startup/reconnection also reconciles storage, covering
  retention gaps or a restored Redis instance. Pending messages are recovered
  explicitly; `XREADGROUP` for new entries alone is insufficient.

The worker holds delivered notifications pending until successful handling. During
execution, cancellation notifications remain unacknowledged until terminal
settlement. Crashes before acknowledgment can repeat delivery, including after a
successful settlement. Terminal state and ownership checks make repeats harmless.
A held execution slot still requires the existing operator recovery procedure.

The browser subscribes with `subscribeBacktests` and unsubscribes with
`unsubscribeBacktests` on the shared WebSocket. The gateway sends
`backtestConnection` with boolean `connected`, including Redis continuity, plus
change and health events. Each subscription/reconnection confirms continuity and
triggers snapshot refreshes. Browser sockets receive broadcasts independently;
they do not compete with worker consumer groups. Changed events coalesce refreshes
of history, selected Backtest and Run, and queue; result artifacts retain their existing
on-demand loading rules. Health updates require no recurring queue read.

HTTP commands and reads remain on backtester-api. The browser retains last-good
data when disconnected, restores subscriptions automatically, and marks missing
health evidence stale locally. For a healthy snapshot, heartbeat age is
`snapshot_at_ms - last_heartbeat_ms`; receiving that snapshot does not restart
the freshness window.
The browser adds locally elapsed time to that age, avoiding comparisons between
absolute browser and server clocks. Browser elapsed-time clocks do not make HTTP calls.
There is no normal periodic backtest-state polling or separate recovery scan.

See [ADR-0008](../adr/0008-backtest-stream-notifications.md) for the deliberate
trade-off between recovery and transactional message publication.

## Order execution snapshots

Request v3 optionally carries `execution_mode=orders`, an explicit `candle_quote`,
price-unit `spread`, and `max_position_quantity`. `intrabar_execution_policy`
generalizes the legacy exit policy without changing old saved requests. New fields
are omitted from legacy snapshot responses unless originally present. Runtime
semantics and strategy authoring are owned by [order contracts](../../backtester/ORDERS.md).

Order-mode Fills retain existing ordered storage and minute timestamps. Diagnostics
persist the order lifecycle in `order_events`. Equity Replay descriptor v1 uses M1
as its timeframe identity and reads M1 candles for these runs; the request timeframe
continues to identify strategy decisions. Target-mode fingerprints are unchanged.
