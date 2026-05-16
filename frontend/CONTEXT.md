# Frontend Context

Vue 3 and Vite application for charting markets, candles, and indicators.

## Owned Interfaces

- Chart UI state for selected Market, Timeframe, Candle history, live Candle
  updates, and Indicators.
- WebSocket client commands and live updates shared with `webserver`.
- Chart series points that convert transport `timestamp_ms` into chart `time`
  epoch seconds.
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
- `src/api/`: HTTP clients for database accessor and indicator API.
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
