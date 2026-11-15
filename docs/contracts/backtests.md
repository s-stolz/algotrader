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

### Market price increments

Acceptance resolves each selected Market's `min_move` from the server catalog and
stores it in the normalized Market selection and the Run request's optional
`market_min_move` field. It is metadata, never a strategy parameter or a client
submission override. Tick-based strategies require a positive, finite increment.
Execution and worker handoff use the saved value without re-reading Market metadata.
Copying a saved Backtest or Run resolves the currently selected Market again at
acceptance. Existing snapshots lacking the field remain readable; their historical
parameters and results are unchanged. This additive field retains request schema v3.

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
Catalog entries also declare `execution_mode` (`targets` by default, or `orders`).
Workspace derives execution mode from the selected strategy; it is not a user
choice. Legacy metadata without this field is treated as target mode.
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

## Execution-log inspection

`GET /backtests/runs/{run_id}/execution-log` is a bounded inspection API for
succeeded result-v3 Runs. Query parameters are `page` (one-based, default 1),
`page_size` (default 10, maximum 100), and `include_unexecuted` (default false).
Invalid bounds return 422; missing Runs return 404; ineligible Runs return 409.
The response is `{run_id, page, page_size, total, items}`. Out-of-range pages
return empty items and retain the total. Existing full Fill/Closed Trade APIs
remain unchanged for chart overlays and analysis.

Each item is either `{kind: "trade", timestamp_ms, trade}` with the existing
Closed Trade payload, or `{kind: "unexecuted_order", timestamp_ms, order}`.
The latter carries `order_id`, `outcome`, nullable `side` (`buy`/`sell`),
`planned_price`, and `planned_quantity`; it is intended activity, not a Fill or
Closed Trade. Only explicit terminal outcomes qualify, one latest terminal event
per order; any recorded Fill event excludes that order. Unknown outcomes and
invalid event timestamps are excluded. Metadata uses the latest explicit field
at or before the terminal event; explicit null clears an older value. Legacy
missing intent remains null. New sizing/submit/ignored-position events retain
side and planned price/quantity where available in both engines.

When a reversal closes an existing Position but its opening portion is rejected,
both engines record the closing `filled` event before the rejection, including
actual filled quantity and price. This excludes partially executed Orders from
the unexecuted list. Historical Runs saved without this event cannot be repaired
unambiguously because saved Fills have no Order identity; rerun them to obtain
complete execution evidence. Do not infer Order/Fill links from timestamps.

Pages sort descending by trade exit/order terminal timestamp, then trade before
order, descending saved sequence/event ordinal, and ascending identity. The
accessor performs the combined projection, count, and LIMIT/OFFSET in one
PostgreSQL statement; diagnostics never cross the service boundary for this
read. Including unexecuted orders still scans the saved diagnostic array inside
PostgreSQL; this is bounded transport, not an indexed order-event store.

Run detail, Run list, and Backtest member reads accept `include_diagnostics=false`
to omit diagnostic data at the storage projection. The default remains true for
existing artifact consumers. Backtest outcome summaries always use lightweight
member reads. No result-schema version or storage migration is required.

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

## Saved profit factor

Shared reporting calculates `metrics.profit_factor` for every engine path from
Closed Trades: sum positive realized PnL divided by the absolute sum of negative
realized PnL. The required JSON value is a finite nonnegative number (including
zero for losses only), `"infinity"` for profits without losses, or explicit `null`
for no trades or only breakevens. Missing values, booleans, negative numbers,
NaN, numeric infinity, and other strings are invalid; null is not zero.

Child handoff, successful settlement, JSONB storage, and public Run/member reads
preserve this union. Failed/cancelled Runs need no successful-result metrics.
Frontend decoding displays infinity as ∞ and null as unavailable. Comparison
uses the saved value without a trade-derived fallback; other trade-based analysis
still loads Closed Trades. Return, drawdown, and ending-equity semantics remain
unchanged. No historical fallback or backfill is provided. Removing temporary
Runs is a user-owned deployment precondition; implementation never deletes data.

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
Successful settlement requires a finite `metrics.ending_equity`, taken from the
final simulated portfolio snapshot (including unrealized PnL). The table reads
this saved metric independently of replay availability. No historical backfill
or replay fallback is provided for this metric.

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

### Streaming Equity Replay

`GET /backtests/runs/{run_id}/equity-curve/stream?max_points=2000` returns
`application/x-ndjson`. Each newline terminates one complete JSON frame:

- `{"type":"preview","equity_curve":[...]}` replaces the previous provisional
  preview. Points use the existing timestamp/equity/drawdown shape. Previews are
  bounded by `max_points` and emitted at most about ten times per second.
- `{"type":"complete","result":{...}}` carries the existing Equity Replay
  response, either `exact` or `unavailable`. Only `exact` is a verified curve.
  Ending equity uses the saved metric, independently of these frames. Final
  sampling preserves the existing extrema/anchors;
  previews can change when the final sample replaces them.
- `{"type":"error","message":"..."}` reports a failed read after HTTP headers
  have been sent. EOF without a terminal frame is also a failed read.

A **Replay Preview** is provisional equity reconstructed from a prefix of current
Candles and saved Fills. It is not a saved result or a verified Equity Replay.
Verification compares the complete existing descriptor before issuing an exact
terminal frame. Fingerprint mismatch discards the preview; saved metrics remain
available. Order-mode replay continues to consume all required M1 Candles, with
immutable instrument identity, multiplier, and the existing sizing cutoff.

The Workspace admits at most two active replay streams and queues other selected
Runs. Returning to All backtests (including browser navigation), leaving the
Workspace, applying to the chart, or deselecting a Run aborts
its stream. Backtester closes its downstream Candle stream, releasing the
accessor cursor/session. A request already performing a bounded batch may finish
that batch; cancellation does not cancel a Backtest or change durable Run state.
Interrupted replays restart on return; completed curves remain cached in the
Workspace. Background refreshes and member changes do not resume hidden analysis.
Failed reads and unavailable replay require explicit Retry.

Partial curves use the chart library's normal fit-to-data timeline, which may
rescale as previews arrive, and the existing loading animation until verification
completes. No additional loading text is required.
Read failure or unavailability removes the affected partial curve and exposes
Retry, preserving other verified curves and saved metrics.

The existing nonstreaming equity endpoint remains available for compatibility.
The new streaming path avoids its unbounded Candle response; callers that keep
using legacy bulk Candle reads can still incur large-response processing costs.


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
- `backtests:events:v1`: JSON `payload` is `backtestChanged`, `backtestHealth`,
  or `backtestProgress`.
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

### Run stage progress

`backtestProgress` carries `run_id` and `stage`: `loading_data`,
`preparing_indicators`, `simulating`, `calculating_results`, or `saving`.
These are ordered milestones, not elapsed-time estimates or equally weighted
work percentages. Both engines use this sequence, including sized-target and
order execution. Event-driven preparation initializes indicators and warmup;
in-window indicator updates remain part of simulation. Saving starts in the
worker parent before durable result settlement. Only lifecycle success means
saving has completed.

Event-driven simulation additionally reports optional `processed_candles` and
`total_candles` integers on `backtestProgress`. Counts measure candles traversed
in the requested window, including in-window warmup but excluding earlier
bootstrap history. Order mode counts prepared M1 execution candles. The total is
fixed for a Run; early account depletion can finish below that total. Vectorized
Runs retain stage-only feedback.

The execution child reports monotonically increasing stage indices and coarse
candle counters through shared memory inherited through the supervisor. It never
publishes to Redis. The parent observes it during existing cancellation checks and queues
coalesced publication. Fast stages may be skipped by observers. Candle counters
update every 1,000 completed candles and at loop exit; observers may coalesce the final count into the next stage. No extra
heartbeat, timer, per-candle stream, or change to terminal child-result messages
is introduced. Progress cannot release an execution slot or settle a Run.

The worker publisher atomically stores the latest progress payload at
`backtests:progress:v1` and appends its notification to the event stream. The
single verified execution slot means one latest-run snapshot per deployment is
sufficient; a new Run replaces it. This bounded Redis snapshot survives event
stream trimming but is advisory and is not a PostgreSQL lifecycle record. If
Redis loses it, the next progress update repopulates it; no progress is invented.

The gateway restores this snapshot on browser subscription and Redis reconnect,
after establishing the event-stream cursor. Browsers cache progress by Run ID
and ignore earlier stages and non-advancing counts within the same stage, since
a snapshot can race a newer event. Counts with a changed total are ignored.
Stage events update only the progress display and do not refresh saved results.
The milestone row appears beneath the existing overall settled-runs bar only
for a running member with known progress. All five labels remain visible;
loading starts at the left edge and saving ends at the right edge. Stage-only
fill reaches the last completed dot and the current dot is outlined.
For event-driven simulation with counts, numeric `processed / total` appears
below Simulating and the fill interpolates from that dot toward Calculating
results. The active stage advances only when the engine reports it. Counts
disappear after simulation; subsequent stages do not move the fill backward.
Terminal or cancelling Runs hide the row even if late progress arrives. The latest stage
remains displayed indefinitely during long work; no progress timeout or ETA is
shown.

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
persist the order lifecycle in `order_events`. Accepted `submit` and `update`
events include the resolved `limit_price` and `side`; timestamps mark when the
order becomes effective. Terminal events end the pending-price segment, and
updates start a new segment. Earlier saved events may omit prices; consumers
must not infer their pending levels. These additive diagnostic fields do not
change the result schema version. Equity Replay descriptor v1 uses M1
as its timeframe identity and reads M1 candles for these runs; the request timeframe
continues to identify strategy decisions. Target-mode fingerprints are unchanged.

## Sizing, instrument valuation, and margin

New Backtest acceptance resolves a linear instrument snapshot for each Run:
`symbol_id`, `settlement_currency`, `contract_multiplier`, `minimum_quantity`,
`quantity_step`, and `min_move`. The symbol's settlement currency is the account
currency. Price changes times quantity times contract multiplier determine PnL;
there is no account-currency conversion. Symbol edits cannot alter these snapshots.
Historical snapshots without sizing retain their original execution semantics.

Setup owns execution sizing (`strategy`, `units`, `exposure`, `equity_exposure`,
`risk`, or `equity_risk`) and independent stop-loss/take-profit selections (`none`,
`strategy`, `percent`, `distance`, or `ticks`). Strategy parameter catalog metadata
`purpose` places dedicated sizing and exit parameters in Setup; those fields are
submitted as constants. Signal parameters remain in Parameters.
The `strategy` mode is labeled **Strategy-provided** for sizing, stop-loss, and
take-profit: the strategy supplies the corresponding quantity or protective value.

Sizing uses submission-time equity including unrealized PnL. Money risk is the
entry-to-stop loss excluding costs, per entry rather than a combined-position cap.
Pending entries use their specified price; next-open market entries use the latest
completed close. Quantity rounds down to the instrument increment. Missing/invalid
risk stops or below-minimum quantities reject the entry with a diagnostic. A target
strategy without an initial stop cannot select strategy-provided risk sizing.
Pending quantities and initial stop information remain fixed until replacement.
Normal strategy exits stay active. Shared protective prices remain fixed after
the first fill until flat; additions use the existing stop. Strategy protection
updates can change only sides whose source is strategy-provided.

Leverage defaults to one and affects margin, not requested exposure. Open-position
margin is current absolute notional divided by leverage; pending entries reserve
estimated margin. Rejection for insufficient available margin does not resize an
entry or end the Run. Recheck affordability at fill, including execution costs.
Closing/reducing orders remain eligible; reversals can close while their new entry
is rejected. Account depletion is an intrabar event: cancel pending orders, close
remaining exposure, preserve negative balances, and stop processing that Run.
It is a successful simulation with `termination_reason=account_depleted`, not an
infrastructure failure. Other Runs continue. There are no broker-specific stop-out
thresholds or margin-call warnings.

Sizing and rejection events are saved in diagnostics and displayed in execution
logs. Replay uses the saved contract multiplier and ends at the saved final point.
Historical Candle reads use stable Market IDs. Market names come only from the
current `markets` row; renamed symbols and exchanges have no alias lookup.
Metadata edits do not rewrite saved requests or Candle data.
