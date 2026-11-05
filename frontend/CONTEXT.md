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
- Opening ranges render as per-session primitives on the Candle series through
  `src/utils/chart/openingRange/`. Calculation coordinates are not plotted as
  price series. Style changes redraw without recalculation; extension visibility
  does not change the range. Historical-only indicators declare `supports_live:
  false`, skip live subscriptions, and display a Historical label.
- Backtest overlays use Closed Trades with explicit direction and saved planned
  protective prices. Selecting a run changes Market/Timeframe but preserves the
  normal latest-Candles, live-update, and lazy-history workflow. Render overlays
  for the loaded range on the main candlestick pane.
  Start at `src/stores/backtestOverlayStore.ts` and
  `src/utils/chart/backtestOverlay.ts`.
- Chart overlay eligibility requires a successful, single-symbol run, an
  available Market, and supported version 3 Closed Trades. The selected run ID
  persists in local storage; validate it again on reload.
- `components/Chart/backtestIndicators.ts` coordinates the selected run's saved
  indicator group after matching Candle history loads. Run-owned indicators use
  distinct local identities, locked calculation parameters, and editable styles;
  manual indicators remain independent. Changing Market/Timeframe removes the
  run-owned group and hides trade/protective overlays while retaining selection.
  Restore returns to the saved context and reloads the group with its styles.
  Superseded loads cannot install indicators. Legacy runs without a snapshot
  retain trade overlays without inferred indicators; see
  [saved chart indicators](../docs/contracts/backtests.md#saved-chart-indicators).
- Measurement Overlays are transient pointer-held comparisons on the main pane:
  exact pointer prices, nearest logical bar slots, inclusive Candle count, and
  signed price/percent deltas relative to the anchor. They clear on release,
  cancellation, or focus loss. Start at
  `src/components/Chart/chartInteractionMode.ts` and
  `src/utils/chart/measurementOverlayLifecycle.ts`.

## Backtest Workspace

- Start at `src/views/BacktestWorkspaceView.vue` and
  `src/stores/backtestWorkspaceStore.ts`; creation lives in
  `src/views/BacktestCreationDrawer.vue`. Its feature-local `creation/` sections
  share `useBacktestCreation.ts`, which owns draft/selection retention, reuse revisions,
  preview generations/debounce cleanup, and submission identity. `src/App.vue`
  keeps routed views alive:
  navigation preserves drafts, history filters, and comparison selections.
- Creation retains an optional experiment name alongside draft fields. Names
  are top-level creation properties; omit them from stateless preview.
  History/detail names and member labels share `backtestWorkspaceRuns.ts`; use
  that displayed name for search and sorting, with UUIDs beneath history labels.
  Validation and exact unnamed text follow
  [experiment names](../docs/contracts/backtests.md#experiment-names), with no metadata fallback.
- Detail names use the shared inline experiment-name control. Drafts belong to
  an edit session; acknowledgements belong to an experiment identity. Explicitly
  committed names remain bound to that identity when navigation replaces or
  unmounts the editor; Escape cancels still-unsent queued intent. Workspace
  name revisions protect older reads and names awaiting readback, while allowing
  fresh confirmed reads to resume normal refreshes. Apply name acknowledgements
  without replacing execution fields from a save response.
- Read history, commands, logs, and Equity Replay through
  `src/api/backtesterClient.ts`. For lifecycle or API changes, read
  [backtest contracts](../docs/contracts/backtests.md); the public backtester API owns
  those policies. Queue availability and position are advisory telemetry.
- `src/utils/useBacktestEvents.ts` shares one backtest WebSocket subscription across
  active consumers. Change/reconnect events refresh saved reads; health events
  update matching worker freshness without polling. The socket restores desired
  subscriptions after reconnect. See [delivery contracts](../docs/contracts/backtests.md#real-time-delivery-and-recovery).
- Failed reads or disconnected delivery retain the last good data and mark live status unknown.
  Ignore superseded responses after changing the inspected Run, Backtest, or draft.
  Background refresh preserves settled charts and inspection state.
- Creation uses the current strategy catalog; historical inspection uses saved
  requests and metadata. Reuse applies the current Strategy Version automatically,
  retains all saved resolved values, including values that originally used defaults. Show
  version changes beside the strategy and schema changes beside parameter fields;
  invalid values still block submission. Keep submission/command identities across retries;
  submission follows explicit user action and a successful current preview.
  `src/views/backtestReuse.ts` proposes editable names from saved top-level names
  with a complete ` (copy)` suffix, shortening by Unicode characters to fit the
  existing limit. Unnamed sources leave the draft empty; copied names use the
  ordinary creation contract and survive draft navigation and mode changes.
- Treat missing metrics separately from zero. Ending equity comes from the last
  exact Equity Replay point; saved Return uses its first-recorded-equity baseline,
  separately from request Initial capital. Tables display maximum drawdown as a
  positive magnitude; replay charts display nonpositive drawdown. Preserve
  backend sampling and expose replay unavailability separately from read errors.
  Comparison helpers live in `src/views/backtestComparison.ts`.
- `BacktestEntryLimitField.vue` edits the independent daily entry cap; empty means
  unlimited. It counts actual entries, not signals, with a UTC reset per run.
  Validation, draft retention, and reuse follow the shared execution contract.
- `BacktestScheduleFields.vue` edits optional UTC daily execution boundaries in
  the shared creation execution controls. Omitted/null schedules are disabled;
  enabled settings survive draft retention and saved Run/Backtest reuse. Validation
  blocks invalid ordering before submission or preview. These are shared
  Backtest settings rather than strategy parameter axes.
- Creation calendar dates convert explicitly to UTC midnight. Chart timestamp
  conversion follows the root transport contract.

## Shared UI and Transport

- Shared visual values, root provider, overlay typography, and justified control
  overrides follow [design ownership](DESIGN.md). `App.vue` provides the theme to
  every workflow; shared controls have no legacy styling mode.
- Use themed `Base*` controls in `src/components/Common/` for tables, drawers,
  selects, grouped selects, dropdowns, popovers, and checkboxes. Shared styling
  lives there and in `src/assets/main.css`; extend these surfaces for consistent
  controls rather than copying per-view theme overrides.
- HTTP clients live in `src/api/`; runtime payload validation belongs in
  `src/types/contracts.ts` or focused validation helpers.
- WebSocket changes start at `src/utils/websocketService.ts`. Read
  [realtime-service context](../realtime-service/CONTEXT.md) for the shared protocol and check
  `test/utils/websocketService.spec.ts` when changing it.
- Timeframe changes start at `src/utils/timeframes.ts`. Follow
  [contract-change guidance](../docs/agent/CONTRACT-CHANGES.md) for supported
  Timeframes across services; chart options alone do not establish support.

## Verification

Frontend gate: `make test frontend`. For targeted commands and test conventions,
read [commands](../docs/agent/COMMANDS.md) and
[coding conventions](../docs/agent/CODING-CONVENTIONS.md).
