# AlgoTrader Context

AlgoTrader is a multi-service experimental trading platform. It collects broker
market data, stores normalized candles, computes indicators, streams live updates
to a chart UI, and supports standalone backtesting.

## Domain Vocabulary

- **Market**: a configured tradable symbol in `markets`, identified by `symbol_id`,
  `symbol`, `exchange`, `market_type`, `min_move`, and `timezone`.
- **Symbol**: broker-facing instrument name such as `EURUSD`. In broker-service,
  cTrader symbol metadata also includes `symbol_id`, `digits`, and commission data.
- **Candle**: OHLCV bar. External/internal JSON uses expanded keys
  `timestamp_ms`, `open`, `high`, `low`, `close`, `volume`.
- **Redis Candle**: compact live stream payload with keys `o`, `h`, `l`, `c`, `v`, `t`.
- **Tick**: bid/ask market data with compact Redis keys `b`, `a`, `t`.
- **Timeframe**: code such as `M1`, `M5`, `H1`, `D1`; support differs between raw
  storage, broker streams, chart options, and Timescale continuous aggregates.
- **Indicator**: computed series derived from candles through `indicator_engine`.
- **Order**: broker command to place or cancel an order.
- **Position**: open broker exposure that can be closed fully or partially.
- **Deal**: broker execution history entry.
- **Backtest**: offline simulation over historical candle data.
- **Backtest Run**: one durable execution of a backtest request. Avoid
  **Strategy Run** for this concept because a strategy can also exist outside a
  completed historical backtest.
- **Cancel Backtest Run**: an irreversible command that stops an unstarted or
  executing Backtest Run. An executing run is `cancelling` after acceptance and
  becomes `cancelled` once its execution has ended; it cannot produce a normal
  result after cancellation is accepted.
- **Backtest Batch**: a durable user-submitted collection of related Backtest
  Runs that preserves why those runs belong together. Membership is immutable
  and nonempty, and is fully materialized when the batch is accepted: the batch
  and all resolved member requests are created atomically, each run belongs to at
  most one batch, and rerunning creates new history rather than changing the
  original batch.
- **Backtest Batch Member**: a Backtest Run belonging to one Backtest Batch,
  identified within that batch by its deterministic Parameter Sweep expansion
  ordinal and immutable resolved request. Standalone Backtest Runs are not batch
  members.
- **Backtest Batch Lifecycle**: the durable control state of a Backtest Batch.
  Its states are `queued`, `running`, `pausing`, `paused`, `cancelling`,
  `completed`, and `cancelled`. Lifecycle is distinct from member outcomes: a
  completed batch may contain any mixture of succeeded, failed, and individually
  cancelled Backtest Runs. The `cancelled` batch state is reserved for a Cancel
  Batch command, not inferred from member outcomes. `running` means member
  scheduling is enabled, even when no member is executing at that instant.
- **Backtest Batch Outcome**: derived counts of member Backtest Run outcomes,
  including queued, running, cancelling, succeeded, failed, and cancelled members. A
  Backtest Batch does not fail as a unit when individual members fail. Its fixed
  total is the immutable membership count; settled progress is the fraction of
  succeeded, failed, and cancelled members, while executed count includes only
  succeeded and failed members.
- **Backtest Batch Lifecycle Revision**: a monotonic version that orders accepted
  batch commands and automatic lifecycle transitions. Concurrent changes follow
  durable commit order, and a retried command retains its original identity
  rather than creating a second transition.
- **Backtest Batch Lifecycle Event**: an append-only historical record of an
  accepted batch command or automatic lifecycle transition, ordered by Backtest
  Batch Lifecycle Revision. It preserves when and why the control state changed
  without treating transient worker details as domain history.
- **Pause Batch**: a reversible command that makes unstarted batch members
  ineligible to run without interrupting an active member. A batch is `pausing`
  while active work drains and `paused` once none is active.
- **Resume Batch**: a command that retracts a pending or completed Pause Batch
  and makes remaining queued members eligible to run again. Its next durable
  turn joins the queue tail after active work settles; repeated command IDs
  return their original revision and result.
- **Cancel Batch**: an irreversible command whose durable acceptance makes every
  nonterminal member ineligible to start or complete normally. Queued members
  and force-terminated active members become cancelled; already terminal member
  results are preserved. The batch is `cancelling` until every member is
  terminal and is then `cancelled`.
- **Delete Backtest Batch**: permanent removal of a completed or cancelled
  Backtest Batch together with all its member runs, results, and lifecycle
  history. Deletion is distinct from cancellation and is unavailable while work
  remains active.
- **Parameter Sweep**: a Backtest Batch whose runs are generated from combinations
  of selected backtest configuration values, such as strategy parameters,
  Markets, and Timeframes. Independently invalid dimension values reject its
  definition; candidates that violate the strategy's cross-parameter validation
  are explicitly reported and excluded before immutable membership is created.
- **Strategy Version**: the developer-assigned, monotonically increasing integer
  paired with a registered strategy identifier and used as the sole declared
  identity of its public parameter contract and behavior. Developers must bump it
  when either changes. A Backtest Run resolves the exact pair and cannot silently
  substitute another version; the version does not identify the complete runtime
  or keep retired strategy code executable.
- **Current Strategy Catalog**: live metadata discovered from registered
  single-file strategy builders. New standalone requests persist the exact
  Strategy Version and resolved defaults; older unversioned requests remain
  inspectable without assigning the current identity.
- **Strategy Parameter Schema**: the public parameter names, types, defaults, and
  independent constraints derived from a registered strategy builder's annotated
  signature. The type itself defines inherent values such as Boolean `true` and
  `false`; explicit choices are reserved for genuinely restricted non-Boolean
  parameters.
- **Strategy Parameter Validation**: validation of one complete resolved strategy
  parameter set. The framework enforces the Strategy Parameter Schema, then an
  optional validator owned by that registered strategy enforces relationships
  between its parameters; standalone runs and Parameter Sweeps use the same path.
- **Strategy Metadata Snapshot**: the immutable copy of a registered strategy's
  identity and public parameter schema captured when a Backtest Batch is accepted,
  so historical configuration remains understandable after registry changes.
- **Backtest Workspace**: the user-facing area for creating and monitoring
  Backtest Runs and Backtest Batches, inspecting their results, and comparing
  selected runs.
- **Backtest Equity Curve**: the time-ordered history of a Backtest Run's
  simulated account equity, used to inspect and compare performance and drawdown
  over time.
- **Equity Replay Fingerprint**: the durable identity of the ordered executable
  Candle timestamps and closing prices used to mark a Backtest Run's persisted
  Fills. Equity replay is exact only when current Candle storage has the same
  fingerprint; replay does not reevaluate strategy signals or indicators.
- **Backtest Fill**: one simulated execution event inside a Backtest Run.
- **Backtest Closed Trade**: one completed simulated round-trip position inside a
  Backtest Run, with trade direction, entry, exit, realized PnL, fees, exit
  reason, and optional planned protective exit prices.

## System Flow

1. `broker-service` connects to cTrader and can fetch accounts, orders, positions,
   deals, symbols, ticks, and trendbars.
2. `broker-service` publishes live ticks and candles into Redis streams.
3. `ingestion-service` consumes live M1 candle streams, backfills gaps through
   broker-service, and writes expanded candles through `database-accessor-api`.
4. `database-accessor-api` reads and writes markets and candles in TimescaleDB.
5. `indicator-api` fetches candles from `database-accessor-api`, computes historical
   indicators, and can publish live indicator streams from Redis candle input.
6. `webserver` starts and stops broker or indicator streams, consumes Redis, and
   fans out WebSocket messages to frontend clients.
7. `frontend` fetches historical candles/indicators and applies live WebSocket
   updates to the chart.
8. `backtester` loads candle history through shared data access and runs selected
   strategy engines. Durable backtest run lifecycle and result records are stored
   through `database-accessor-api`.

## Data Contracts

- All service APIs use UTC epoch milliseconds for transport timestamps.
- Frontend chart points use `time` as epoch seconds only after converting from
  `timestamp_ms`.
- Redis stream names:
  - candles: `candles:{account_id}:{symbol}:{timeframe}`
  - ticks: `ticks:{account_id}:{symbol}`
  - indicators: `indicators:{account_id}:{exchange}:{symbol}:{timeframe}:{stream_id}`
- Timescale stores M1 candles in `candles`. Higher timeframe reads may use
  continuous aggregates or direct bucketing.
- Broker historical trendbar routes use cTrader-style query names `fromTs` and `toTs`.
- Database accessor routes use `start_ms` and `end_ms`.
- Durable backtest runs use `queued`, `running`, `cancelling`, `succeeded`, `failed`,
  and `cancelled`
  lifecycle states. Lifecycle timestamps are normalized storage fields; the
  complete immutable request is versioned JSON, and fills/trades are normalized
  child records. New request schema version 3 adds exact Strategy Version and
  resolved parameters; version 2 remains readable. Both use explicit Allowed
  Directions rather than legacy `allow_short`. New results use schema version 3;
  older result versions remain readable. Closed trades carry nullable `stop_loss_price` and
  `take_profit_price` planned levels plus explicit trade direction so consumers
  do not infer long or short trades from fill order. Run history filters request
  attributes from that JSON document and returns matches by `submitted_at DESC`,
  then `run_id ASC`.
- Accepted Backtest Batches use a versioned normalized sweep definition, immutable
  Strategy Metadata Snapshot, fixed candidate/member/excluded counts, and
  contiguous zero-based member ordinals. A batch and all resolved member request
  snapshots commit atomically under a unique client submission identity. Existing
  standalone runs retain null batch identity. Batch members are excluded from the
  standalone claim path. The global queue has one durable turn per standalone
  run or eligible batch. A batch turn claims the lowest queued ordinal and
  rejoins the tail after settlement if work remains. The single slot, turn
  consumption, member outcome, and automatic batch transition commit atomically.
  Revisioned batch events retain prior and new status for automatic transitions;
  accepted revision-zero and legacy events have a null prior status.
- New successful single-Market bar-mode runs atomically store an Equity Replay
  descriptor with metrics, diagnostics, Fills, and Closed Trades. The descriptor
  fingerprints executable Candle timestamps and closes; legacy successes retain
  metrics and logs without a descriptor. Exact curves are reconstructed on read
  from matching Candles and saved Fills, never stored as full curves.
- Frontend and other non-storage consumers read durable backtest run history,
  fills, and trades through the public backtester API. `database-accessor-api`
  remains the primitive persistence API behind the backtester boundary.
- Backtest execution uses one durable database slot. A claim atomically
  occupies it and moves the next queued standalone run or batch member to `running`; fenced terminal
  persistence releases it only after child exit is confirmed. An interrupted
  run becomes `failed` with `worker_interrupted` after verified worker shutdown;
  queued history remains queued. Operational slot faults are separate from
  durable run outcomes.
- Cancel Run accepts a queued standalone/member run as terminal `cancelled`, or
  marks a running run `cancelling` while retaining its slot. Only confirmed
  child-tree exit and fenced settlement complete cancellation and release the
  slot. The acceptance timestamp, source, and reason remain durable. Individual
  member acceptance advances its batch lifecycle revision and appends a member
  command event even when the batch control state is unchanged.
- The backtester-owned queue snapshot projects the durable slot and global
  queue with independent worker heartbeat telemetry. Its advisory positions and
  availability never change run lifecycle or release a held slot.
  Public queued batch entries identify the batch and expose a null Run ID; the
  worker-facing queue state retains the next member Run ID for claims.

## Change Guidance

- Treat this file as the canonical cross-service contract summary.
- When changing Candle, Tick, Timeframe, WebSocket, or storage behavior, use
  `docs/agent/CONTRACT-CHANGES.md` and `docs/CONTEXT-MAP.md` to find affected
  producer and consumer contexts.
- Keep implementation details in area contexts or reference docs; this file should
  stay small enough to read at agent startup.
