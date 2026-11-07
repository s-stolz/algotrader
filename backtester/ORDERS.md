# Order-based backtests

Set `execution.execution_mode` to `orders` and explicitly set `candle_quote` to
`bid`, `ask`, or `mid`. Supply an `OrderStrategyModel` on the strategy definition.
The registered `limit_reversion` version 1 example places two-sided OCO limits
and takes profit in two equal portions. Existing strategies retain target-based,
next-open execution unless order mode is selected.

## Two clocks

`request.timeframe` remains the strategy timeframe. Its completed candles produce
commands; fills and equity use M1 candles. Market-data runs load both resolutions
(reusing M1 for an M1 strategy). Caller-provided runs pass `execution_bars` for
higher-timeframe strategies. They must actually contain M1 data; timestamp spacing
alone cannot establish a candle's aggregation interval. No coarse fallback occurs.

Commands carry the **close boundary**, not the strategy candle's opening timestamp.
A decision at 10:10 first affects the minute opening at 10:10. Execution of the
preceding minute happens before that decision. Monthly closes use calendar months.
Warmup supplies indicators but emits no orders. Unfinished strategy candles do not
produce commands. Array builders must use causal calculations, just as existing
vectorized strategies must; sequential builders only receive the previous and
current completed feature snapshots.

`OrderStrategyModel.build_commands(features, close_timestamps)` produces an array
of commands. `evaluate_close(close_timestamp, previous, current)` implements the
same decisions sequentially. The vector runtime merges commands into one minute
scan and uses cumulative portfolio arrays. The event runtime owns independent
matching and sequential cash/position updates. Both have bounded path evaluations
per minute and matching work proportional to the active orders and touched levels;
there is no scan of every historical order for every minute.

## Order lifecycle

- `submit`: provide a new run-unique ID and a complete `LimitOrder`.
- `update`: provide a complete replacement with the same active ID. Submission
  priority is retained. Missing/filled/cancelled/expired IDs produce an
  `inactive_noop` diagnostic; updates never recreate orders.
- `cancel`: remove the referenced active order; inactive IDs are recorded no-ops.
- `protect`: replace the net position's protection using `OrderProtection`.
  A flat position produces an inactive no-op.

Orders persist until filled, cancelled, or expired. Optional expiry is exclusive
and minute-aligned. At 10:30 an order expiring at 10:30 cannot fill or be updated
back into existence. Run end expires remaining orders; open positions retain the
existing mark-to-market treatment. Commands without a remaining execution minute
are recorded as `run_end_unexecuted`.

Orders specify trade quantities, not desired positions. Buys and sells adjust one
net position. `reduce_only` caps an exit to the remaining opposing exposure and
never reverses it. All other fills execute their whole quantity or none; liquidity,
queue position, and partial order fills are not modeled. `oco_group` cancels
siblings on a fill, including a reduce-only capped fill.

`max_position_quantity`, allowed directions, daily entry limits, and entry windows
are checked against actual exposure at execution. Violations cancel the whole
order and record `constraint_cancelled`. Target-array sizing/risk transforms are
rejected for order strategies; order builders own quantities, and execution
configuration owns exposure limits. Scheduled exits close remaining exposure at
the first valid minute open at or after the deadline and cancel pending entries.

## Protection

`OrderProtection` supports one fixed stop and multiple `TakeProfitTier` prices.
Each tier specifies either an absolute quantity or a fraction. A `protect` command
resolves fractions against current exposure once, at submission. An entry's attached
protection resolves fractions against that entry order's submitted quantity, which
is already fixed; it becomes active on the fill. Attaching new protection explicitly
replaces existing position protection. Entries without attached protection retain
the existing levels and tier quantities.

Fixed levels do not move with additional entries. Optional `stop_loss_pct` and
`take_profit_pct` instead follow the net average entry price; the latter is one
full-position target and cannot be combined with fixed tiers. A partial take
profit consumes its tier, retains other tiers, and keeps the stop over the entire
remainder. Going flat cancels protection. A stop-out also cancels pending entries.
Position protection is separate from entry OCO groups.

## Prices and ambiguous minutes

`spread` is a fixed price-unit difference between ask and bid, not bps or pips.
For bid candles ask is candle price plus spread; for ask candles bid is candle
price minus spread; for mid candles the offsets are half the spread. The quote
convention is an explicit run assumption because the storage contract does not
identify it. Buy limits match ask; sells match bid. Touches qualify, favorable
opening gaps improve price, and adverse `slippage_bps` is bounded by a limit price.
Market-like stop/scheduled exits can slip beyond their trigger. Commission is
charged separately on executed notional.

`intrabar_execution_policy` is `conservative`, `optimistic`, or `error`. The legacy
`intrabar_exit_policy` remains accepted and maps to the corresponding behavior;
conflicting explicit choices are rejected. Each minute evaluates O-H-L-C and
O-L-H-C paths. Conservative/optimistic chooses lower/higher closing equity for
that minute, with O-H-L-C as a deterministic tie-break. Error rejects different
execution outcomes. All prices are evaluated causally along each path, so a target
reached before entry cannot close that entry. At an identical price protection
executes before entries, and independent entries use submission order.

This is a documented OHLC path model, not the worst/best possible tick history.
Prices can oscillate more often than either path. Diagnostics record ambiguous
minutes. Fills identify the minute, not a fabricated intraminute timestamp.

Missing minutes produce `execution_gap` diagnostics. `skip` retains pending orders,
`expire` cancels orders exposed to the gap, and `error` rejects the run. Without a
market-session calendar, closed-market intervals and missing observations cannot
be distinguished reliably; both are reported rather than silently guessed.

## Saved results and scope

`diagnostics.order_events` preserves submissions, updates, cancellations, fills,
expiry, constraint failures, ambiguity, and gaps. Ordered Fills and partial Closed
Trades use existing persistence. Equity Replay fingerprints and fetches M1 closes
for order mode while the immutable request retains the strategy timeframe.

Minute-level strategy decisions inside unfinished higher-timeframe candles,
ticks, liquidity simulation, hedged positions, and Workspace order-authoring
controls remain outside this version.
