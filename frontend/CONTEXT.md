# Frontend Context

Vue 3 and Vite application for charting markets, candles, and indicators.

## Owned Interfaces

- Chart UI state for selected Market, Timeframe, Candle history, live Candle
  updates, and Indicators.
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
- Backtest marker labels assume the current long-only backtester contract:
  entries are buys and exits are sells until short-capable trades add explicit
  side fields.
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
  fields for planned protective exit lines.
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
