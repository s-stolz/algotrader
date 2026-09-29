# Frontend Context

Vue 3 and Vite application for charting markets, candles, and indicators.

## Owned Interfaces

- Chart UI state for selected Market, Timeframe, Candle history, live Candle
  updates, and Indicators.
- Chart Interaction Mode controls what pointer drag does on the candlestick
  pane. Pan is the default mode for scrolling through the chart; Measure enables
  transient Measurement Overlays. A selected mode remains active until the user
  selects another mode. Measure mode takes over primary left-button pointer drag
  only; wheel-based zooming and horizontal chart navigation remain available.
  Mobile touch gestures are outside the initial Measurement Overlay behavior.
  Measure mode uses a crosshair-style cursor over the candlestick pane. Chart
  Interaction Mode controls belong above the chart with the other chart controls
  and use circular icon-only buttons: `HandRightOutline` for Pan and
  `ExpandOutline` for Measure. Pan is selected by default, and the active mode
  uses the same turquoise border and icon color as the other top-bar buttons use
  on hover, without filling the button. Changing modes cancels any active
  Measurement Overlay. Changing market, timeframe, or chart session does not
  change the selected Chart Interaction Mode. Chart Interaction Mode is not
  persisted across page refreshes. Measure can be selected without loaded Candle
  data, but Measurement Overlays require Candle data to exist.
- Historical indicators align to the currently loaded candle range: newly
  applied or refreshed indicators render the latest batch first, backfill older
  batches until they cover loaded candles, and trim indicator points outside the
  loaded candle timestamp range.
- WebSocket client commands, control acknowledgements, errors, and live updates
  shared with `webserver`.
- Chart series points that convert transport `timestamp_ms` into chart `time`
  epoch seconds.
- Backtest run history and execution-log visualization consumed through the
  public backtester API, not direct database-accessor storage routes.
- The Workspace polls the public `/backtests/queue` snapshot while open. It
  treats unreachable or invalid reads as unknown while retaining the timestamp
  of the last good snapshot; availability and advisory standalone queue
  positions are telemetry, not durable lifecycle or an ETA.
- Queue entries identify either one standalone Run or one eligible Batch. The
  Workspace shows an active Batch member ordinal, the next queued member ordinal,
  batch outcome counts, and advisory position from the public snapshot. Batch
  detail refreshes saved counts, active/next ordinals, first-started/terminal
  timestamps, and ordered lifecycle events with nullable prior status, new
  status, and triggering Run IDs. A completed
  Batch can include failed members while successful member results remain usable.
- Parameter Sweep detail separates the saved strategy identity, settled progress,
  member outcome counts, and active/next run context. Its segmented bar shows
  successful, failed, cancelled, running, and stopping members against the fixed
  total; only terminal member outcomes contribute to the displayed percentage.
  Elapsed wall time includes pauses and stops at the saved terminal timestamp.
  Dates are readable UTC values. Accepted selections and an activity timeline
  expand on demand, with full saved JSON and command identifiers in nested details.
  Failed polling retains the last snapshot and explicitly marks live status unknown.
- Batch history Market, Timeframe, Strategy, and failed-member filters use saved
  actual-member context and outcome fields, not the sweep's broader selections
  that may contain excluded candidates.
- Batch detail offers Pause when queued/running and Resume when pausing/paused.
  The control request keeps its command identity across a failed retry and
  retires that identity when a newer lifecycle revision is observed or an
  opposite command succeeds. It refreshes saved status, revision, members, and
  events after acceptance.
  Pausing is shown as active work draining, without a percentage estimate.
- Frontend development proxy exposes the public backtester API under
  `/api/backtester`.
- The Workspace creation drawer reads the live `/backtests/strategies` catalog,
  authoritative Market records, and supported Timeframe codes. It submits an
  exact strategy/version pair to `POST /backtests` and preserves its draft across
  chart navigation. A stale version refreshes metadata for explicit review,
  without substitution or automatic resubmission.
- The creation drawer also builds Parameter Sweep drafts with independent numeric
  Constant/Values/Range controls and one editable field per exact string value,
  including empty and multiline strings. It automatically calls the stateless
  `/backtests/sweeps/preview` route after valid edits, ignores superseded
  responses, and reviews all bounded candidates with local paging, status
  filtering, and deterministic sorting. Sweep submission remains gated until
  batch execution ships; preview creates no saved history.
- Runtime run readers accept request schema versions 2 and 3. Version 2 has no
  declared Strategy Version; history labels it unavailable instead of assigning
  current code. Version 3 includes resolved parameter defaults.
- Backtest chart overlays use Backtest Closed Trades as the primary artifact;
  Backtest Fills are lower-level execution-log records, not the default chart
  overlay.
- Backtest Closed Trade entry and exit markers label the executed action and
  price, such as `Buy @ 101.25` and `Sell @ 104.50`; exit reason is not marker
  label text.
- Backtest entry markers use arrows and exit markers use circles; green means
  buy and red means sell. Coincident reversal exits and entries remain separate.
  Hovering a marker shows Open/Close and trade direction in the overlay panel,
  with saved realized PnL in account units for exits.
- Backtest marker labels must use closed-trade direction for short-capable
  results. Long trades enter with buy markers and exit with sell markers; short
  trades enter with sell markers and exit with buy markers.
- The standalone submission drawer keeps Allowed Directions in execution settings
  and defaults it to `long_and_short`; runtime contracts, run-history metrics,
  and chart overlays read result schema version 3 closed-trade direction.
- Backtest protective exit overlays show configured stop-loss and take-profit
  levels for each closed trade whenever the run's strategy defined them,
  regardless of whether the trade exited by signal, stop loss, or take profit.
  The frontend reads these planned prices from closed-trade API fields rather
  than deriving them from strategy parameters.
- Selecting a Backtest Run from history moves the chart workspace to the run's
  symbol, exchange, and timeframe before drawing its closed-trade overlay.
- Selecting a Backtest Run does not load the full backtest date range at once.
  The chart keeps its normal latest-candles workflow, live updates, and older
  candle lazy loading; backtest trade overlays are applied for the candle ranges
  currently loaded into the chart.
- Backtest overlay v1 fetches all closed trades for the selected run once and
  filters them locally to the currently loaded candle range; range-filtered trade
  reads are a later optimization.
- The selected Backtest Run overlay persists by run ID in local storage and is
  reloaded after browser refresh when the run remains available.
- Backtest overlays are removable chart annotations applied only to the main
  candlestick pane, not indicator panes.
- Measurement Overlay is a transient chart overlay used to compare one
  candlestick-pane point to another while the pointer is held, and is limited to
  the main candlestick pane. Its price comparison uses exact pointer price
  levels, not snapped candle OHLC values.
  Its horizontal endpoints use the nearest logical bar slots to the pointer
  positions.
  Its displayed price and percent deltas preserve upward or downward direction,
  and percent delta is measured relative to the anchor price. Its candle count is
  inclusive of both endpoint logical bar slots, including slots without loaded
  Candle data. Its value label shows price delta, percent delta, and candle
  count; follows the current pointer endpoint; and remains bounded by the chart
  pane. Positive deltas include a `+` sign, negative deltas include a `-` sign,
  and zero deltas have no sign. The UI labels the count as candle/candles. If the
  anchor price is zero, percent delta is shown as `N/A`. Price delta precision
  follows the active Market min move, and percent delta uses two decimals; these
  are display formats applied after calculating from raw pointer-derived prices.
  Avoid "drawing tool" for this concept unless the overlay becomes persistent or
  editable. The overlay is removed when the pointer is released, measurement is
  cancelled, or the window loses focus. Horizontal drag direction only changes
  the measured span; vertical drag direction controls the signed price and
  percent deltas. Its box uses the exact endpoint price levels as vertical bounds
  rather than snapping to candle highs or lows. Its box uses endpoint logical bar
  slot centers as horizontal bounds, even though the candle count is inclusive. A
  zero-span measurement still appears immediately on pointer hold. Its box uses a
  semi-transparent fill and one-pixel solid border with color encoded by price
  direction. It coexists with chart crosshair and OHLC legend updates.
- Backtest overlays expose a compact candlestick-pane panel showing the applied
  run context and a remove action; saved run selection is in the Workspace.
- A shared edge link opens the full-screen Backtest Workspace from the chart's
  right edge and returns to Chart from the Workspace's left edge. Its 64 × 176
  hit area exactly matches the revealed icon-and-arrow control; it opens on hover
  or keyboard focus and hides immediately on pointer exit. Its background is
  `#18222e`. The chart route is
  kept alive, and the Workspace store retains its selected run and editable
  creation draft when navigating between them.
- Workspace history reads saved standalone runs and accepted Batches from the
  public backtester API on entry and at five-second intervals while active.
  One sortable table provides search and status, type, Market, Strategy,
  Timeframe, and With failed runs filters. History checks every five seconds;
  Check now sits beside that status and becomes Retry now on read errors.
  Create Backtest remains the primary header action, and All backtests belongs
  above an analysis page's heading. Failed reads
  report unknown lifecycle state without replacing previously loaded records
  with an empty history.
- Workspace history presents accepted Batches beside standalone summaries in
  that table.
  Opening a Batch reads its saved definition, Strategy Metadata Snapshot,
  revision/events, and actual ordinal-ordered member runs; members do not appear
  again as top-level standalone rows. Missing member metrics remain absent.
- History offers Create from this for standalone runs and Batches. It copies the
  immutable standalone request or the Batch's accepted definition into the
  existing editable drawer, retaining ordered Market/Timeframe/direction choices
  and numeric range inputs. The drawer keeps the draft across chart navigation,
  refreshes current metadata and preview, requires explicit review when the
  Strategy Version changed, and blocks unavailable saved Markets or parameters
  until corrected. Submission uses fresh run or batch identity; saved history is
  untouched and no source link is persisted.
- Sweep submission appears only when the backend advertises controlled batch
  acceptance. The drawer retains one client submission identity across retries
  of an unchanged draft and requires a fresh successful preview after rejection;
  it never automatically resubmits.
- Startup reconciliation appears through these same public history reads as a
  durable failed run with `worker_interrupted`; queued runs remain queued.
  Process ownership and execution-slot faults are operational data, not run
  history fields.
- The current-backtest table shows the selected saved request and metrics.
  Saved Return retains its first-recorded-equity baseline; maximum drawdown is
  displayed as a positive magnitude and PnL as signed account units. Missing
  results and zero-trade values remain distinct. Ending equity is not inferred
  from saved Return.
- Opening a Batch feeds its ordinal-ordered members into the same combined
  settings/performance table used for standalone inspection. Comparison IDs are
  scoped to that open Batch or standalone Run and survive
  sorting, column changes, and execution-log inspection. Only successful rows
  are selectable for comparison; failed, cancelled, and unfinished rows retain
  request settings and missing result metrics. Frontend run readers accept
  cancelling/cancelled statuses for future durable cancellation responses.
- Run analysis fetches all members and sorts them locally before paginating with
  Naive UI. Page sizes are 20 (default), 50, 100, and All. The header comparison
  checkbox selects or deselects successful runs on the current page, preserving
  selections on other pages. Sorting or opening another analysis resets the page;
  page navigation and size changes do not fetch members or select runs.
- One Columns popover controls visible columns with grouped checkboxes for
  Run settings, Performance, and Long / short. Each group has a checked, unchecked,
  or indeterminate checkbox that changes only that group.
  Column settings update immediately and independently of analysis reads; toggling
  a column does not fetch data or remount the table. Ending equity shows a cell
  skeleton during its initial replay read, retains an existing value during
  refresh, and returns to a missing value on unavailable or failed initial reads.
  All saved named strategy parameters remain available in Run settings and the
  selected request. The comparison table pins selection and Run identity,
  horizontally scrolls readable columns, and caps long bodies at 360px beneath
  fixed headers. Differing request assumptions are called out without ranking.
- Selected successful runs read detail and exact Equity Replay through the
  public backtester API. The shared Lightweight Charts view overlays stable
  run-identified equity and nonpositive drawdown series below the table.
  Per-run replay unavailability or read errors leave other series and saved
  metrics intact. Ending equity comes only from the last exact replay point.
- Equity and drawdown comparison charts remain fitted to the full selected
  history on data changes and resize, with chart scrolling and scaling disabled.
  A compact legend identifies runs; series titles never cover the curves.
  Drawdown uses a nonpositive, zero-anchored percentage axis with adaptive
  precision for small losses. Backend sampling is retained and disclosed once
  beside the legend; successful replay details are shown in the metrics table.
- Workspace history explicitly deletes terminal `succeeded`, `failed`, or
  `cancelled` standalone runs and entire `completed` or `cancelled` batches
  through the public backtester API. It refreshes history on success, retains
  visible records on failure, and clears deleted selections and chart overlays.
- Run analysis identifies rows and replay legends by one-based member number
  (standalone runs use #1), with the full Run ID available on hover. The pinned
  Run column follows a narrow, headerless comparison checkbox column and sorts
  by that number. Comparison checkboxes use dark empty and disabled surfaces,
  turquoise selection, and visible keyboard focus. A separate pinned Actions
  column groups execution-log and Open on chart icons, with Cancel shown only
  for queued or running runs. The Actions column contracts when no cancel action
  is available. History also hides unavailable Cancel actions. Chart opening
  acts directly on that row without changing inspection or comparison selection; unavailable actions explain why in a
  tooltip.
- Workspace run cells open a per-run execution-log drawer through the public
  backtester `/trades` and `/fills` resources. Closed Trades and Fills retain
  their stored sequence and separate direction/side semantics. Log reads occur
  on demand and cannot change the selected run or saved metrics; stale reads
  after switching or closing the drawer are ignored. Runs without a completed
  supported log show a disabled log action with an explanation.
- Backtest Run selection requires the run's Market to still exist in the
  frontend Market list; missing Markets leave the current chart unchanged and
  show an explanation in the Workspace.
- Backtest Run chart selection supports single-symbol runs only; runs with zero
  or multiple symbols remain visible in history but are not selectable for the
  single-chart overlay.
- Workspace history shows all lifecycle states, but only `succeeded` runs are
  selectable for chart overlays.
- Workspace standalone rows and opened batch members offer Cancel while queued
  or running. `cancelling` remains unsettled and explains that execution cleanup
  is pending; `cancelled` appears only after verified active exit and settlement
  or immediate queued cancellation. Command refreshes history and queue state.
- Workspace batch detail offers Cancel Batch from queued, running, pausing, and
  paused states. Its command identity survives retry after a lost response.
  The detail refresh shows cancellation acceptance, preserved member outcomes,
  and an unsettled cancelling state until active cleanup commits; queue health
  continues to show any held slot or operational fault.
- Backtest Run chart overlays require result schema version 3 closed trades,
  including planned protective exit levels and explicit trade direction.
- Runtime validation for frontend-facing HTTP and WebSocket payloads.

## Key Modules

- `src/components/Workspace/WorkspaceNavigation.vue`: shared viewport layout and
  accessible edge navigation between Chart and Backtests. Keeps long backtest
  content scrollable within the viewport, moves keyboard focus to the destination
  screen, and respects reduced motion. ChartView owns its flex layout so the chart
  fills the remaining height without vertical page scrolling. App retains both
  route instances with KeepAlive; workspace navigation does not reset drafts,
  filters, or selected comparisons.

- `src/components/Common/BaseCheckbox.vue`: shared native checkbox with dark
  empty/disabled surfaces, turquoise selection, and keyboard focus. Use it for
  all checkbox controls, including run selection and labeled form inputs.
  Supply `indeterminate` for Naive UI group checkboxes with mixed selection.
- `src/components/Common/BasePopover.vue`: shared Naive UI popover with the
  drawer's dark surface, text, borders, and typography; forwards props, events,
  and slots and supports local theme overrides. The Columns popover shows its
  full content without internal scrolling, with viewport margins.
- `src/components/Common/BaseSelect.vue`: shared Naive UI select for Workspace
  history, creation, and execution-log dropdowns. It forwards select props,
  events, and slots while applying the dark control and menu theme. The Workspace
  config provider uses the same theme for Naive UI pagination size pickers.

- `src/components/Common/BaseDrawer.vue`: shared Naive UI side panel with the
  app's dark blue background, text, dividers, and typography. Use it for drawers;
  it forwards Naive UI drawer props, events, and slots, and merges optional
  `theme-overrides` for local customization.

- `src/components/Common/BaseDataTable.vue`: shared Naive UI data table with the
  app's dark blue surfaces, header typography, and keyboard focus styling.
  Fixed columns share subtly lighter header/body surfaces, including striped,
  hover, and sorted states, plus Naive UI boundary shadows. History and run
  analysis use this same treatment without local background overrides. Use it
  for data tables; it accepts Naive UI table props, events, slots, and optional
  `theme-overrides` for local customization. Data tables use columns and data;
  custom control tables supply table sections through the default slot. Both
  render through Naive UI with its themed horizontal and vertical scrollbars.
- `src/views/ChartView.vue`: page-level chart workspace.
- `src/components/Chart/ChartArea.vue`: visual chart wiring, chart infrastructure
  lifecycle, legend updates, and session adapter construction.
- `src/components/Chart/chartSession.ts`: active market/timeframe session workflow,
  live candle subscription ownership, historical candle fetch guards, live-tail
  buffering, indicator refresh sequencing, and older history paging decisions.
- `src/stores/`: Pinia stores for markets, current market, timeframe, candles,
  indicators, and modals.
- `src/api/`: HTTP clients for database accessor, indicator API, and backtester
  API.
- `src/utils/websocketService.ts`: WebSocket client and inbound message validation.
- `src/utils/timeframes.ts`: frontend Timeframe options and conversion helpers.
- `src/utils/chart/`: Lightweight Charts wrappers.
- `src/types/contracts.ts`: runtime validators and TypeScript contract types.

## Change Triggers

- `ChartArea.vue` delegates session workflow to `chartSession.ts`. When changing
  chart workflows, check for duplicate rules in `chartSession.ts`,
  `candlesticksStore.ts`, `ChartManager.ts`, and `indicatorsStore.ts`.
- `contracts.ts` is the runtime validation surface for frontend API data.
- If the WebSocket protocol changes, update `webserver/CONTEXT.md` and
  `frontend/test/utils/websocketService.spec.ts`.
- If Timeframe support changes, inspect `src/utils/timeframes.ts`,
  `database-accessor-api/CONTEXT.md`, `broker-service/CONTEXT.md`, and
  `timescaledb-init/CONTEXT.md`.

## Verification

- Frontend gate: `make test frontend`.
- Prefer store, utility, or WebSocket tests for behavior that does not need a full
  Vue mount.

- The Workspace reads exact Equity Replay from the public backtester route for
  one selected successful run. It preserves `timestamp_ms` through transport and
  converts to chart seconds only for Lightweight Charts. Ending equity comes
  from the final exact point; saved Return keeps its first-recorded-equity
  baseline and request Initial capital remains separate. The UI distinguishes
  sampled curves, specific unavailable reasons, and temporary read errors.

- Workspace history and current-backtest analysis occupy separate page surfaces
  at `/backtests` and `/backtests/:kind/:id` in the existing memory router. The
  kept-alive workspace retains history filters, pagination, comparison selection,
  and drafts while moving between those pages or the chart.
- Creation dates use Naive UI calendars with formatted calendar dates converted
  explicitly to UTC midnight. Background polling retains settled replay curves,
  chart instances, execution-log tabs and filters; it never supersedes a pending
  automatic queue or batch read. Explicit refresh may supersede stale reads.
