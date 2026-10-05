# Backtest Contracts

Read for changes to run/batch lifecycle, strategy identity, durable history, or
Equity Replay. This is the shared contract reference linked by
[root context](../../CONTEXT.md). Backtester owns domain policy and the public
API; the accessor owns atomic storage, and shared clients pass documents through.

## Requests and Strategy Identity

- A **Backtest Run** is one durable execution with an immutable resolved request.
  Current request schema version 3 records exact Strategy Version and defaults;
  version 2 remains readable without inventing a current strategy identity.
  Both use Allowed Directions rather than legacy `allow_short`.
- **Strategy Version** is the positive, monotonically increasing integer paired
  with a registered strategy ID. Bump it for public parameter or behavior
  changes. It identifies the declared strategy contract, not the complete runtime,
  and does not retain retired code for execution.
- The **Current Strategy Catalog** comes from annotated single-file builders.
  Their signatures define the **Strategy Parameter Schema**: names, order,
  types, defaults, and independent constraints. Boolean choices are inherent;
  explicit choices restrict non-Boolean parameters.
- **Strategy Parameter Validation** resolves the schema first, then applies an
  optional pure strategy validator for cross-parameter relationships. Standalone
  submissions and sweeps use the same path without loading Candles.
- Queued requests with unavailable exact versions, including unversioned legacy
  requests, fail before Candle loading with `strategy_version_unavailable`.
  Already executing children retain loaded code; saved history remains readable.
- **Create from this** opens an editable draft against the current catalog from a
  saved request or batch definition. Submission creates independent history;
  changing Strategy Version requires explicit review in the Workspace. Named
  sources propose their saved top-level name plus ` (copy)` in the editable
  creation draft; shorten the source portion by Unicode characters to retain
  the suffix within 120 characters. Unnamed sources leave the draft empty.
  Submissions use the ordinary naming contract with fresh Run/Batch identity
  and never rename, mutate, or link the source experiment.

## Experiment Names

Standalone runs and whole batches carry one nullable top-level `name`, outside
immutable execution requests and accepted sweep definitions. Creation accepts
that field separately; list/detail responses return the saved field. Members
have null names and display their existing zero-based ordinal as `Run #N` with
one-based presentation. Strategy names and versions keep their own meaning.

Names allow duplicates. Absent, empty, or whitespace-only values normalize to
null; surrounding whitespace is trimmed. Reject any line separator (including
CR/LF and Unicode line separators) in nonempty names before trimming, and names longer than 120
Unicode characters after trimming. Frontend, public API, and storage apply the
same rules. `run_metadata.name` and `run_metadata.label` are rejected on new
submissions; unrelated metadata remains supported. Sweep preview does not accept
a name and remains stateless; batch acceptance persists the name separately
without copying it into members or the accepted definition. Retrying a batch
submission retains its original accepted name, alongside its immutable definition.

V017 transfers usable legacy names once, choosing metadata `name` before `label`
(and falling back to a usable label when the name is invalid). Standalone names
come from their request metadata; batch names come from accepted shared-request
metadata. Invalid old values become null. V017 removes only those two metadata
keys from run requests (including members) and accepted shared requests. This
transactional cleanup is the explicit one-time exception to snapshot immutability;
identities, artifacts, lifecycle, membership, and unrelated metadata are preserved.
There is no legacy naming fallback after migration.

Workspace history, details, and name sorting/search use the saved name or exactly
`Unnamed standalone run` / `Unnamed parameter sweep`. History and member rows
show shortened UUIDs underneath; existing details/tooltips retain full IDs.
Search matches a trimmed, case-insensitive whole-query substring against each
individual displayed-name, full ID, submission ID, status, strategy ID, Market,
or Timeframe field and combines with existing dropdown filters.

## Runs and Results

Run states are `queued`, `running`, `cancelling`, `succeeded`, `failed`, and
`cancelled`. Submission persists a queued request and returns `202` with its
location, without executing the engine. Only success exposes result artifacts;
failures expose bounded sanitized errors while tracebacks stay in worker logs.

- **Backtest Fill:** one simulated execution event, with execution side.
- **Backtest Closed Trade:** a completed round trip with explicit long/short
  direction, entry/exit, realized PnL, fees, exit reason, and nullable planned
  `stop_loss_price` / `take_profit_price`. Direction comes from the trade record,
  not fill order; planned prices may differ from actual exit prices.
- New results use schema version 3; older result versions remain inspectable.
  Lifecycle timestamps are normalized storage fields, requests are versioned
  JSON, and Fills/Closed Trades are normalized, per-run sequence-ordered children.
- History filters request attributes from immutable JSON; ordering is
  `submitted_at DESC`, then `run_id ASC`, without pagination. Existing runs with
  no log artifacts return empty lists; missing runs return not found.
- **Cancel Backtest Run** is irreversible. Queued standalone/member runs become
  `cancelled` immediately. Running runs become `cancelling` and retain their slot
  until confirmed process-tree exit and fenced settlement. Acceptance time,
  source, and reason are durable; repeats retain the original acceptance.
  Succeeded/failed runs conflict. Accepted cancellation prevents normal completion.
  Individual member cancellation advances batch revision and records a command
  event even if batch control state stays the same.
- Delete permits terminal standalone runs (`succeeded`, `failed`, `cancelled`) or
  entire settled batches (`completed`, `cancelled`). Active work and direct member
  deletion conflict. Storage rechecks under the slot lock and deletes artifacts,
  members, command receipts, and events atomically with their parent.

## Batches and Sweeps

A **Backtest Batch** preserves why a fixed, nonempty collection of runs belongs
together. Each **Backtest Batch Member** has one immutable resolved request and a
contiguous zero-based member ordinal; a run belongs to at most one batch.
Standalone runs have null batch identity. Rerunning creates new history.

A **Parameter Sweep** expands selected Markets, Timeframes, and parameter axes.
Invalid independent dimension values reject the definition. Cross-parameter
rejections are reported as excluded candidates before membership is created.
Preview deduplicates typed values, bounds the raw product before validation,
returns every Ready/Excluded row, and writes no history. Candidate ordinals retain
full-grid positions; member ordinals cover only accepted candidates.

Acceptance revalidates against current Markets, catalog, and candidate limit.
The batch, all members, normalized definition, counts, initial event, and
**Strategy Metadata Snapshot** commit together. The snapshot preserves strategy
identity and public parameter schema for historical inspection. Retrying the same
submission ID returns the accepted batch for an identical normalized definition;
a changed definition conflicts.

**Backtest Batch Lifecycle** is control state: `queued`, `running`, `pausing`,
`paused`, `cancelling`, `completed`, or `cancelled`. `running` means scheduling is
enabled even between members. **Backtest Batch Outcome** is derived member counts;
a completed batch can include failures and individual cancellations. Only Cancel
Batch makes the batch `cancelled`. Settled progress counts succeeded, failed, and
cancelled members; executed count includes only succeeded and failed members.

- **Pause Batch:** blocks unstarted members; active work drains through `pausing`
  to `paused` without interruption.
- **Resume Batch:** retracts a pending/completed pause and restores eligibility.
  Remaining work joins the queue tail after active work settles.
- **Cancel Batch:** accepts from queued/running/pausing/paused. One transaction
  removes its turn, cancels queued members, marks active work cancelling, and
  records acceptance provenance. Terminal results remain. The batch becomes
  `cancelled` only once every member is terminal.
- **Backtest Batch Lifecycle Revision:** monotonic ordering of commands and
  automatic transitions by durable commit order. Caller command IDs are stable
  across retries; receipts return the original status/revision, including no-ops.
- **Backtest Batch Lifecycle Event:** append-only transition/command history,
  ordered by revision, with prior/new state. Initial revision-zero and legacy
  events have null prior state. No-op receipts add no transition event.

## Execution Slot and Queue

One durable database slot covers claim through terminal persistence. A claim
atomically consumes the earliest eligible turn and marks its run `running`.
There is one turn per standalone run or eligible batch; a batch claims its lowest
queued ordinal and rejoins the tail after settlement if work remains. Settlement
commits outcome, artifacts, batch transition/event, next turn, and slot release
in one owner-token-fenced transaction. Batch members cannot use legacy standalone
claiming; tokenless lifecycle writes cannot commit worker outcomes once the slot
is installed, including after a manual clear.

The slot has no expiry. Release requires verified child-tree exit and reaping.
Uncertain exit or terminal persistence failure retains capacity and exposes an
operational fault. Startup reconciles interrupted work only with a free, unfaulted
slot: running becomes `failed/worker_interrupted`, accepted cancelling becomes
cancelled, and queued history remains queued. See
[worker recovery](../operations/backtest-worker-recovery.md) before clearing a slot.

Queue positions and worker heartbeat availability are advisory, separate from
run outcomes. They cannot release capacity. Public queued batch entries identify
the batch with null `run_id`; primitive queue state retains the next member ID for
claims. A heartbeat must match a held slot's owner to establish its freshness.

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
