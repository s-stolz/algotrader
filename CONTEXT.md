# AlgoTrader Context

AlgoTrader collects broker market data, stores candles, computes indicators,
streams live charts, and runs historical backtests.

## Vocabulary

- **Market:** configured instrument identified by `symbol_id`, with `symbol`,
  `exchange`, `market_type`, `min_move`, and `timezone` metadata.
- **Symbol:** broker-facing instrument name, such as `EURUSD`; broker metadata
  and stored Market identity must be resolved at their boundary.
- **Candle:** OHLCV bar; expanded JSON fields are `timestamp_ms`, `open`, `high`,
  `low`, `close`, and `volume`.
- **Redis Candle:** compact live Candle payload: `o`, `h`, `l`, `c`, `v`, `t`.
- **Tick:** bid/ask data; compact Redis fields are `b`, `a`, `t`.
- **Timeframe:** code such as `M1` or `H1`. Broker streams, storage aggregates,
  and chart options support different sets.
- **Indicator:** series derived from Candles through `indicator_engine`.
- **Order / Position / Deal:** broker command, open exposure, and execution
  history entry respectively.
- **Backtest Run:** one durable historical simulation, with an immutable request
  and lifecycle. Use this term rather than Strategy Run.
- **Backtest Batch:** an immutable, nonempty collection of related Backtest Runs.
  A **Parameter Sweep** generates its members from configuration combinations.
- **Experiment Name:** optional organizational `name` on a standalone Backtest
  Run or whole Backtest Batch, separate from immutable execution snapshots.
  Saved names seed editable Create from this drafts with independent identities.
  A name-only command changes this metadata in any lifecycle state.
  Members use one-based `Run #N` presentation; see [backtest contracts](docs/contracts/backtests.md#experiment-names).
- **Backtest Workspace:** UI for creating, monitoring, inspecting, and comparing
  runs and batches.

For run/batch commands, Strategy Version, saved results, or Equity Replay, read
[backtest contracts](docs/contracts/backtests.md). For simulation and trade
terminology, read [backtester context](backtester/CONTEXT.md).

## System Flow

`broker-service` publishes cTrader ticks and candles to Redis.
`ingestion-service` consumes closed M1 candles, backfills through the broker, and
writes through `database-accessor-api` to TimescaleDB. `indicator-api` calculates
historical and live series using `libs/indicator_engine`. `webserver` manages
source subscriptions and fans Redis updates out to the frontend over WebSocket.

`backtester` loads historical candles through `libs/db_accessor_client`; its API
queues requests and its worker executes them. It owns lifecycle policy and the
public history API; `database-accessor-api` supplies persistence primitives.
Frontend backtest consumers go through the backtester API.

## Shared Contracts

- API and Redis transport timestamps are UTC epoch milliseconds. Frontend chart `time`
  becomes epoch seconds only after conversion from `timestamp_ms`.
- Redis stream names:
  - Candles: `candles:{account_id}:{symbol}:{timeframe}`
  - Ticks: `ticks:{account_id}:{symbol}`
  - Indicators: `indicators:{account_id}:{exchange}:{symbol}:{timeframe}:{stream_id}`
- Broker historical trendbars use `fromTs` / `toTs`; database candle queries use
  `start_ms` / `end_ms`.
- Timescale stores M1 candles in `candles`; higher Timeframes use continuous
  aggregates or direct bucketing.
- WebSocket message shapes are owned by [webserver context](webserver/CONTEXT.md).
- Durable run/batch invariants are owned by
  [backtest contracts](docs/contracts/backtests.md), including versioned snapshots,
  cancellation, and the execution slot that remains held until verified exit.

This file owns the cross-service summary. Update a focused reference for detailed
contracts and an area context for local responsibilities. Use the
[contract-change map](docs/agent/CONTRACT-CHANGES.md) to identify affected consumers.
