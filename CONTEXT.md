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
- **Backtest:** a saved definition and its nonempty collection of historical
  simulations. Fixed inputs and varying configurations use the same model.
- **Run:** one execution within a Backtest, with an immutable resolved request
  and lifecycle; displayed by ordinal as `Run #N`.
- **Experiment Name:** optional organizational name of a Backtest, separate from
  immutable execution snapshots.
- **Backtest Workspace:** UI for creating, monitoring, inspecting, and comparing
  Backtests and their Runs.

For Backtest/Run commands, Strategy Version, saved results, or Equity Replay, read
[backtest contracts](docs/contracts/backtests.md). For simulation and trade
terminology, read [backtester context](backtester/CONTEXT.md).

## System Flow

`broker-service` publishes cTrader ticks and candles to Redis.
`ingestion-service` consumes closed M1 candles, backfills through the broker, and
writes through `database-accessor-api` to TimescaleDB. `indicator-api` calculates
historical and live series using `libs/indicator_engine`. `realtime-service` manages
source subscriptions and fans Redis updates out to the frontend over WebSocket.

`backtester` loads historical candles through `libs/db_accessor_client`; its API
queues requests and its worker executes them. It owns lifecycle policy and the
public history API; `database-accessor-api` supplies persistence primitives.
Frontend backtest commands and saved reads go through the backtester API.
Redis Streams wake workers for queue/cancellation checks and carry change and
health events through `realtime-service` on the shared browser WebSocket. Startup
and reconnection reconcile durable state; normal operation does not poll it.
Delivery and recovery details live in the
[backtest contract](docs/contracts/backtests.md#real-time-delivery-and-recovery).

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
- WebSocket message shapes are owned by [realtime-service context](realtime-service/CONTEXT.md).
- Durable Backtest/Run invariants are owned by
  [backtest contracts](docs/contracts/backtests.md), including versioned snapshots,
  cancellation, and the execution slot that remains held until verified exit.

This file owns the cross-service summary. Update a focused reference for detailed
contracts and an area context for local responsibilities. Use the
[contract-change map](docs/agent/CONTRACT-CHANGES.md) to identify affected consumers.
