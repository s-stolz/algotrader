# Shared Libraries Context

## Database Accessor Client

`db_accessor_client` owns sync/async HTTP transport, Candle DataFrame conversion,
and shared Python Timeframe helpers. Centralize reusable Timeframe behavior here.

- DataFrames use UTC timestamp indexes; `include_timestamp_ms=True` also preserves
  expanded timestamp fields for JSON-style callers.
- Backtest methods pass versioned requests, results, replay descriptors, command
  identities, and queue/heartbeat primitives through unchanged. Backtester owns
  policy and public projections; the accessor owns transactions. Read
  [backtest contracts](../docs/contracts/backtests.md) when changing those payloads.
- Keep sync and async behavior aligned, including empty 204 deletion responses,
  404/409 errors, ordered execution logs, and conditional-operation `updated` flags.
- Candle shape changes affect the accessor, indicator-api, and backtester.

## Indicator Engine

`indicator_engine` owns NumPy batch/streaming computation. UI metadata and transport
formatting belong to indicator-api/frontend. Both engines share registry definitions.

- `BarTensor`: aligned data shaped `(time, asset, field)`.
- `Tensor`: outputs shaped `(time, asset, output, param)`.
- `ParamGrid`: deterministic parameter combinations.
- `HistoryPolicy`: rolling or unbounded streaming history.
- NaNs propagate; the engine does not forward-fill.

For usage and shape examples, read [indicator engine README](indicator_engine/README.md).

## Logging and Verification

`algotrader_logger` owns shared logging and request middleware.
Use `make test db_accessor_client` or `make test indicator_engine`, plus affected
consumer tests when shared interfaces change.
