# Registering a backtest strategy

Put one strategy builder in a single Python file under `src/strategies/examples/`
or `src/strategies/custom/`. Decorate it with `register_strategy(strategy_id,
strategy_version)` from `strategies.registry`. The identifier stays stable;
increase the positive integer version whenever the public parameters **or
executable behavior** change. The live catalog publishes only the current
version. Retired code is not retained for future execution.

Annotate every public builder parameter with `bool`, `int`, `float`, `str`, or
`T | None`. Signature order is catalog and sweep order. A parameter with
no default is required; a default is materialized into each accepted immutable
request. Use `Annotated[T, ParameterInfo(...)]` only for numeric minimum/maximum,
restricted numeric/string choices, descriptions, or display names. Boolean
choices are implicit. Keep internal constants in the builder body, not in its
signature. There is no second registry manifest to update.

An optional decorator `validator` receives the fully resolved parameter mapping.
It must be pure and deterministic: no Candles, clock, network, database, or
mutable external state. For an expected invalid relationship, call
`reject_combination("field_one", "field_two", message="Safe explanation")`.
Other exceptions are configuration errors and do not become ordinary validation
issues. Keep any independent bounds in `ParameterInfo` so they can be shown
before submission.

New public submissions must use the exact catalog `(strategy_id,
strategy_version)` pair. A stale pair is rejected; the client refreshes the
catalog and requires explicit review. Already saved requests remain immutable.
Queued work with an unavailable exact version fails closed, while historical
requests and results remain inspectable.

## Scope and verification

A routine strategy addition consists of a registered builder and one focused
test file. Capture signal, exit/reversal, and filtered-signal behavior in the
builder docstring and behavioral tests. Keep strategy-specific explanations
beside the builder; this guide owns the shared authoring process.

Test qualifying and rejected signals, boundary cases, and resulting position
behavior. Reuse existing registry, direction-mapping, and transport coverage
rather than repeating it for each strategy. Add tests at a shared component's
boundary when its behavior changes, representative engine integration coverage
when execution or feature evaluation changes, and API/storage tests when their
contracts change. Missing indicators or engine capabilities expand the scope
beyond a routine strategy addition and need their own regression coverage.

Follow [workflow](../docs/agent/WORKFLOW.md) for selecting verification gates.

## Indicator inputs

`IndicatorFeatureRequirement` selects an indicator output and may name an
`output_asset` for aggregate outputs. Required input Markets and calculation
history come from the installed indicator specification. They do not expand the
run's single traded Market. All input candles use the run's exchange and Timeframe.

The application runner also derives the saved Chart Indicator Snapshot from
these requirements. Declare each calculation used for features here; multiple
outputs with identical resolved parameters are displayed as one indicator.
Snapshots include installed parameter defaults and use engine string IDs,
independently of numeric chart catalog IDs. See
[saved chart indicators](../docs/contracts/backtests.md#saved-chart-indicators)
for persistence and legacy-result behavior.

Multi-source and anchored indicators require a declarative bar model. Anchored
indicators must provide incremental updates for sequential execution. Real-data
runs load each source once per requested interval and predecessor query.
Caller-supplied `run_backtest` calls provide additional sources through
`feature_bars`, keyed by the indicator's exact asset names; these calls never
fetch missing data. An omitted source is a configuration error; a supplied empty
source makes its features unavailable.

Daily anchored inputs require timeframe-aligned candles within the indicator's
declared session window and timezone. Session boundaries must align with the
Timeframe. Currency strength requires the full UTC day through each decision,
with the preceding available close seeding each source independently, including
across closures. Opening ranges require only their formation window and no
predecessor. Missing or nonfinite required inputs invalidate the remainder of
that local day causally, without changing earlier values. Gaps outside the
required window do not invalidate a completed range. Each new day evaluates
completeness again. No input is forward-filled.

`indicators_available` is a reserved feature: unavailable values suppress entry
signals, including short entries, without deleting executable candles. In
direction-restricted runs, exit signals based on still-available features remain
eligible. Protective and scheduled exits continue independently. Source bootstrap
initializes calculations without emitting signals; crossover decisions use only
in-window snapshots in both engines.

## Explicit exits

`BarStrategyModel.flat_conditions` is an optional tuple of conditions combined
with OR. A matching condition emits `StrategySignal.FLAT`, distinct from hold
(`0`) and the directional signals (`1` and `-1`). It takes priority over both
directional conditions and their filters, even when `indicators_available` is
false. Its own operands must still be available and finite.

The action sets the raw target to zero in all direction modes. Normal sizing and
risk transforms still apply. It cancels a deferred entry when the resulting
target is flat, closes existing exposure at the next executable open, and does
nothing when already flat. Gap policies, final-bar expiry, and protective exit
priority remain unchanged; completed exits retain the `signal` reason. A flat
condition alone is not a wall-clock schedule or an execution-time entry cutoff.

## Daily execution schedule

Set `BarStrategyModel.daily_schedule` to a `DailyTradingSchedule` from
`domain.schedule` to constrain actual fills. Its integer UTC minutes define an
inclusive entry start, an exclusive last-entry cutoff, and a same-day exit time.
The required ordering is `0 <= start < last_entry <= exit < 1440`; omitted
schedules preserve unrestricted execution. Builders can expose these boundaries
as ordinary saved strategy parameters. No separate request or result schema is
required.

Both engines check the destination bar's open timestamp, including for deferred
orders. Outside the entry window, exposure increases are cancelled; a direction
flip may close existing exposure but cannot open the opposite position. Pending
entries from a previous UTC day are discarded, and expired desired targets reset
at the day boundary so new signals can trade again.

Each entered position retains its entry day's exit deadline. At or after that
deadline the engine requires a flat target, independently of feature availability
or sizing transforms. It uses the first available open, including after missing
candles or an overnight gap. Invalid opens follow `gap_policy`; a still-open
overdue position requests an exit again on each subsequent bar, even when the
previous attempt expired. Nothing is filled beyond the run's data/end boundary.
These clock-triggered actions use known calendar boundaries and do not inspect
future prices. Ordinary decisions retain next-open execution.

Scheduled closes use normal fees, slippage, and the `signal` exit reason. Existing
stop/target gap-through priority remains in effect. Intrabar protection still
applies to positions that remain open. Schedules do not count entries or enforce
a daily entry limit.
