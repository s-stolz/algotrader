# Shared Libraries Context

Shared Python packages used by multiple services.

## Owned Interfaces

- `db_accessor_client` HTTP clients, Candle DataFrame conversion, and Python
  Timeframe helpers.
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
