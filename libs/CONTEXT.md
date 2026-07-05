# Shared Libraries Context

Shared Python packages used by multiple services.

## Owned Interfaces

- `db_accessor_client` HTTP clients, Candle DataFrame conversion, and Python
  Timeframe helpers.
- Synchronous and asynchronous durable backtest run create/get/list/delete,
  fill/trade retrieval, conditional update, and successful-completion methods.
- `indicator_engine` batch and streaming compute interface.
- `algotrader_logger` shared logging helpers and request middleware.

## Libraries

- `libs/db_accessor_client`: sync and async HTTP clients for database-accessor-api,
  candle DataFrame conversion, and canonical Python Timeframe helpers.
- `libs/indicator_engine`: NumPy-first indicator computation library with batch
  and streaming update engines.
- `libs/algotrader_logger`: shared logging helpers and request middleware.

## Indicator Engine Concepts

- `BarTensor`: dense aligned market data shaped `(time, asset, field)`.
- `Tensor`: indicator output shaped `(time, asset, output, param)`.
- `ParamGrid`: deterministic parameter grid for reproducible indicator runs.
- `HistoryPolicy`: rolling or unbounded history control for streaming updates.
- Batch engine and update engine should share indicator definitions through the
  registry.

## Contracts

- `db_accessor_client` returns pandas DataFrames indexed by UTC timestamps.
- `include_timestamp_ms=True` preserves expanded timestamp fields for callers
  that need JSON-style records.
- `indicator_engine` intentionally propagates NaN and does not forward-fill.
- `db_accessor_client.create_backtest_run` and `get_backtest_run` pass versioned
  durable run documents through unchanged, including request schema version 2
  Allowed Directions. Lifecycle policy and domain mapping remain in backtester.
- Synchronous and asynchronous `list_backtest_runs` methods pass optional
  lifecycle, immutable-request, and submission-date filters without pagination
  or queue-selection behavior.
- Conditional run updates and successful completion return whether the accessor
  atomically matched the caller-provided expected status.
- Execution-log methods pass ordered normalized fill/trade records through
  unchanged, including result schema version 3 closed-trade direction and result
  schema version 2 planned protective exit prices, and deletion accepts the
  accessor's `204 No Content` response.

## Change Triggers

- Prefer centralizing shared Timeframe behavior in `db_accessor_client` before
  copying maps into services.
- Keep UI metadata out of `indicator_engine`; indicator-api and frontend own
  presentation metadata.
- If Candle DataFrame shape changes, inspect `database-accessor-api`,
  `indicator-api`, and `backtester` contexts.

## Verification

- Indicator engine tests: `make test indicator_engine`.
- Run affected consumer tests when shared client interfaces change.
