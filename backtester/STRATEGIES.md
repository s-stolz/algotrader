# Registering a backtest strategy

Put public strategy builders under `src/strategies/examples/` and local-only
builders under `src/strategies/custom/`, one builder per Python file. Decorate it
with `register_strategy(strategy_id, strategy_version)` from
`strategies.registry`. The identifier stays stable;
increase the positive integer version whenever the public parameters **or
executable behavior** change. The live catalog publishes only the current
version. Retired code is not retained for future execution.

Annotate every public builder parameter with `bool`, `int`, `float`, `str`, or
`T | None`. Signature order is catalog and parameter order. A parameter with
no default is required; a default is materialized into each accepted immutable
request. Use `Annotated[T, ParameterInfo(...)]` only for numeric minimum/maximum,
restricted numeric/string choices, descriptions, or display names. Boolean
choices are implicit. Keep internal constants in the builder body, not in its
signature. There is no second registry manifest to update.

Order builders declare `execution_mode="orders"` on `register_strategy`; the
Workspace uses this catalog metadata to configure execution automatically.
Target builders keep the default `targets`.

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

## Private strategy workspace

`src/strategies/custom/` is ignored by Git and Docker build contexts, except for
its tracked package initializer. Keep that initializer generic; place local
builders in separate `.py` files. The registry discovers direct modules in this
package using the same decorator, version, parameter validation, and catalog as
public examples. No manifest or registry edit is needed. Duplicate IDs are
rejected rather than replacing a public strategy.

Keep strategy-specific tests, notes, documentation, presets, and exports under
`backtester/private/` (relative to the repository root). This whole workspace is
also excluded from Git and Docker build contexts. Suggested subdirectories are
`tests/`, `notes/`, `docs/`, `presets/`, and `outputs/`. Generic framework changes
and synthetic framework tests remain in the normal tracked directories.

From `backtester/`, run private tests explicitly with:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s private/tests -p 'test_*.py'
```

Local Compose mounts the same `backtester/` directory into the API and worker,
so both can load local modules without including them in the image. Standalone
images contain only public strategies unless a private workspace is mounted at
runtime. Discovery is cached per process: after adding or changing a local
builder, reload the API and worker together while idle, following the
[worker restart safeguards](../docs/operations/backtest-worker-recovery.md).

Git ignores prevent ordinary staging; they do not remove already tracked files
or prevent forced staging. Check `git ls-files src/strategies/custom private`
from `backtester/`: only the generic package initializer should be tracked.
Names and parameters of installed local strategies remain visible to clients of
the local API, and saved runs remain in the local database. Export those records
only into the ignored workspace when they contain private strategy details.

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
`output_asset` for aggregate outputs. Instead of a fixed `output_key`, it may
provide `output_key_by_symbol`, an explicit mapping from traded Symbol to output
key. Unlisted Symbols fail closed; selection does not add executable Markets or
change the indicator's chart configuration. Required input Markets and calculation
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

### Daily feature capture

An `IndicatorFeatureRequirement` can set `capture_at_utc_minute` to an integer
from 1 through 1439. The feature captures the output of the candle closing at
that UTC minute, then holds it for the rest of that candle's UTC day. Before
capture it is unavailable. Missing or invalid cutoff output leaves it unavailable
for that day; a later value never substitutes for the cutoff. A new day resets
the capture. Timeframes must divide the UTC day and align with the cutoff.

Capture is an optional strategy feature transformation; it does not change the
indicator calculation or its saved chart configuration. Omitted capture settings
retain ordinary continuously updated features. A captured value remains valid
when subsequent inputs are missing; declare an uncaptured requirement as well
when decisions also need current input availability. Both engines consume only
completed candles. The loader includes the current day's capture history and
indicator warmup even when a run starts after the cutoff.

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

Set `ExecutionConfig.daily_schedule` to a `DailyTradingSchedule` from
`domain.schedule` to constrain actual fills. Its integer UTC minutes define an
inclusive entry start, an exclusive last-entry cutoff, and a same-day exit time.
The required ordering is `0 <= start < last_entry <= exit < 1440`; omitted
schedules preserve unrestricted execution. The schedule belongs to the run
execution configuration, not the strategy builder. It is saved and reused with
each Run's request. Backtest members can have different schedules when creation
selects schedule alternatives. See the
[schedule selection contract](../docs/contracts/backtests.md#shared-execution-controls)
for `daily_schedules`, resolved Run requests, and legacy shared schedule input.
Declarative bar strategies support schedules in both engines; callback-only
vectorized strategies reject an enabled schedule.

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
applies to positions that remain open. The optional daily entry limit below applies independently.

## Daily entry limit

`ExecutionConfig.max_entries_per_day` is an optional positive integer; omitted or
null means unlimited. It works independently of the daily schedule for declarative
bar strategies. The count belongs to the run and resets on the UTC date of the
executing candle. Shared Backtest settings apply independently to each Run.

Each actual fill that opens or increases exposure counts once. A reversal counts
as one new entry for its opening portion. Signals, cancelled/expired orders,
reductions, and exits do not count. An entry followed by a protective exit on the
same candle still counts. At the limit, exposure increases are cancelled and a
reversal may close the old position without opening the opposite position.
Protective, scheduled, and explicit exits remain eligible. Deferred entries count
on their actual fill day, subject to any separately enabled schedule restrictions.

## Persistent limit orders

See [order strategy contracts](ORDERS.md) for the dual evaluator interface, minute
execution, protective tiers, costs, and the registered `limit_reversion` example.

## Setup-owned sizing and protective settings

Annotate dedicated builder parameters with `ParameterInfo(purpose="sizing")`,
`purpose="stop_loss"`, or `purpose="take_profit"` to place them in Setup. The
builder still receives resolved values, so old saved parameter dictionaries remain
readable. These controls are constants in the creation UI. Shared sizing and exit
sources are selected independently of these strategy-provided values; strategy
signal exits remain active. See [sizing and margin](../docs/contracts/backtests.md#sizing-instrument-valuation-and-margin)
for submission-time sizing, pending-order reservations, and account depletion.

Quantities are instrument units rather than lots. `contract_multiplier` supplies
the value per quantity unit; do not apply leverage to a strategy's requested size.
The engine rounds quantities and enforces margin for strategy-defined sizing too.
