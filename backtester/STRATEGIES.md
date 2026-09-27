# Registering a backtest strategy

Put one strategy builder in a single Python file under `src/strategies/examples/`
or `src/strategies/custom/`. Decorate it with `register_strategy(strategy_id,
strategy_version)` from `strategies.registry`. The identifier stays stable;
increase the positive integer version whenever the public parameters **or
executable behavior** change. The live catalog publishes only the current
version. Retired code is not retained for future execution.

Annotate every public builder parameter with `bool`, `int`, `float`, `str`, or
`T | None`. Signature order is catalog and future sweep order. A parameter with
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
