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
  and use circular icon-only buttons with hover tooltips: `HandRightOutline` for
  Pan and `ExpandOutline` for Measure. Pan is selected by default, and the active
  mode has a visible selected state. Changing modes cancels any active
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
- Frontend development proxy exposes the public backtester API under
  `/api/backtester`.
- Backtest chart overlays use Backtest Closed Trades as the primary artifact;
  Backtest Fills are lower-level execution-log records, not the default chart
  overlay.
- Backtest Closed Trade entry and exit markers label the executed action and
  price, such as `Buy @ 101.25` and `Sell @ 104.50`; exit reason is not marker
  label text.
- Backtest marker labels must use closed-trade direction for short-capable
  results. Long trades enter with buy markers and exit with sell markers; short
  trades enter with sell markers and exit with buy markers.
- Short-support frontend work is consumer-side unless a backtest submission UI
  already exists: update runtime contracts, run-history metric display, and
  chart overlay labels for result schema version 3 closed-trade direction.
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
  run context and a remove action; run selection remains in the Backtest Run
  history modal.
- Backtest Run history modal loads runs when opened, supports lightweight
  client-side status/text filtering, and does not include a dedicated refresh
  control in v1.
- Backtest Run history can delete terminal `succeeded` or `failed` runs through
  the public backtester API; deletion removes the run and its execution logs from
  storage, while queued/running deletion is left to future cancellation behavior.
- Opening the Backtest Run history modal fetches the latest run list from the
  backtester API; closing and reopening refetches.
- Backtest Run selection requires the run's market to still exist in the
  frontend market list; missing markets leave the current chart unchanged and
  surface an error instead of creating an incomplete chart market.
- Backtest Run chart selection supports single-symbol runs only; runs with zero
  or multiple symbols remain visible in history but are not selectable for the
  single-chart overlay.
- Backtest Run history shows all lifecycle states, but only `succeeded` runs are
  selectable for chart overlays.
- Backtest Run chart overlays require result schema version 2 closed-trade
  fields for planned protective exit lines. Short-capable overlays require
  result schema version 3 closed-trade direction.
- Runtime validation for frontend-facing HTTP and WebSocket payloads.

## Key Modules

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
