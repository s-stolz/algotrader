# Frontend Context

Vue chart workspace and Backtest Workspace. Domain vocabulary and cross-service
contracts live in [root context](../CONTEXT.md); this file covers frontend seams
and behavior that is easy to break when changing them.

## Chart Sessions and Overlays

- `src/components/Chart/ChartArea.vue` wires rendering and lifecycle adapters;
  `chartSession.ts` beside it owns market/timeframe transitions, live Candle
  subscriptions, fetch guards, live-tail buffering, and older-history paging.
  Keep session sequencing there. Related state and rendering live in
  `src/stores/candlesticksStore.ts`, `src/stores/indicatorsStore.ts`, and
  `src/utils/chart/ChartManager.ts`.
- Historical Indicators cover the loaded Candle range: load the latest batch
  first, backfill older batches, and trim points outside that range.
- Backtest overlays use Closed Trades with explicit direction and saved planned
  protective prices. Selecting a run changes Market/Timeframe but preserves the
  normal latest-Candles, live-update, and lazy-history workflow. Render overlays
  for the loaded range on the main candlestick pane.
  Start at `src/stores/backtestOverlayStore.ts` and
  `src/utils/chart/backtestOverlay.ts`.
- Chart overlay eligibility requires a successful, single-symbol run, an
  available Market, and supported version 3 Closed Trades. The selected run ID
  persists in local storage; validate it again on reload.
- Measurement Overlays are transient pointer-held comparisons on the main pane:
  exact pointer prices, nearest logical bar slots, inclusive Candle count, and
  signed price/percent deltas relative to the anchor. They clear on release,
  cancellation, or focus loss. Start at
  `src/components/Chart/chartInteractionMode.ts` and
  `src/utils/chart/measurementOverlayLifecycle.ts`.

## Backtest Workspace

- Start at `src/views/BacktestWorkspaceView.vue` and
  `src/stores/backtestWorkspaceStore.ts`; creation lives in
  `src/views/BacktestCreationDrawer.vue`. `src/App.vue` keeps routed views alive:
  navigation preserves drafts, history filters, and comparison selections.
- Read history, commands, logs, and Equity Replay through
  `src/api/backtesterClient.ts`. For lifecycle or API changes, read
  [backtest contracts](../docs/contracts/backtests.md); the public backtester API owns
  those policies. Queue availability and position are advisory telemetry.
- Failed polling retains the last good data and marks live status unknown.
  Ignore superseded responses after changing the inspected run, batch, or draft.
  Background refresh preserves settled charts and inspection state.
- Creation uses the current strategy catalog; historical inspection uses saved
  requests and metadata. Require review of changed Strategy Versions before
  reuse. Keep submission/command identities across retries of the same action;
  submission follows explicit user action and advertised backend capability.
- Treat missing metrics separately from zero. Ending equity comes from the last
  exact Equity Replay point; saved Return uses its first-recorded-equity baseline,
  separately from request Initial capital. Tables display maximum drawdown as a
  positive magnitude; replay charts display nonpositive drawdown. Preserve
  backend sampling and expose replay unavailability separately from read errors.
  Comparison helpers live in `src/views/backtestComparison.ts`.
- Creation calendar dates convert explicitly to UTC midnight. Chart timestamp
  conversion follows the root transport contract.

## Shared UI and Transport

- Use themed `Base*` controls in `src/components/Common/` for tables, drawers,
  selects, grouped selects, dropdowns, popovers, and checkboxes. Shared styling
  lives there and in `src/assets/main.css`; extend these surfaces for consistent
  controls rather than copying per-view theme overrides.
- HTTP clients live in `src/api/`; runtime payload validation belongs in
  `src/types/contracts.ts` or focused validation helpers.
- WebSocket changes start at `src/utils/websocketService.ts`. Read
  [webserver context](../webserver/CONTEXT.md) for the shared protocol and check
  `test/utils/websocketService.spec.ts` when changing it.
- Timeframe changes start at `src/utils/timeframes.ts`. Follow
  [contract-change guidance](../docs/agent/CONTRACT-CHANGES.md) for supported
  Timeframes across services; chart options alone do not establish support.

## Verification

Frontend gate: `make test frontend`. For targeted commands and test conventions,
read [commands](../docs/agent/COMMANDS.md) and
[coding conventions](../docs/agent/CODING-CONVENTIONS.md).
