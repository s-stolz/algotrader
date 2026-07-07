# AlgoTrader Context

AlgoTrader is a multi-service experimental trading platform. It collects broker
market data, stores normalized candles, computes indicators, streams live updates
to a chart UI, and supports standalone backtesting.

## Domain Vocabulary

- **Market**: a configured tradable symbol in `markets`, identified by `symbol_id`,
  `symbol`, `exchange`, `market_type`, `min_move`, and `timezone`.
- **Symbol**: broker-facing instrument name such as `EURUSD`. In broker-service,
  cTrader symbol metadata also includes `symbol_id`, `digits`, and commission data.
- **Candle**: OHLCV bar. External/internal JSON uses expanded keys
  `timestamp_ms`, `open`, `high`, `low`, `close`, `volume`.
- **Redis Candle**: compact live stream payload with keys `o`, `h`, `l`, `c`, `v`, `t`.
- **Tick**: bid/ask market data with compact Redis keys `b`, `a`, `t`.
- **Timeframe**: code such as `M1`, `M5`, `H1`, `D1`; support differs between raw
  storage, broker streams, chart options, and Timescale continuous aggregates.
- **Indicator**: computed series derived from candles through `indicator_engine`.
- **Order**: broker command to place or cancel an order.
- **Position**: open broker exposure that can be closed fully or partially.
- **Deal**: broker execution history entry.
- **Backtest**: offline simulation over historical candle data.
- **Backtest Run**: one durable execution of a backtest request. Avoid
  **Strategy Run** for this concept because a strategy can also exist outside a
  completed historical backtest.
- **Backtest Fill**: one simulated execution event inside a Backtest Run.
- **Backtest Closed Trade**: one completed simulated round-trip position inside a
  Backtest Run, with trade direction, entry, exit, realized PnL, fees, exit
  reason, and optional planned protective exit prices.

## System Flow

1. `broker-service` connects to cTrader and can fetch accounts, orders, positions,
   deals, symbols, ticks, and trendbars.
2. `broker-service` publishes live ticks and candles into Redis streams.
3. `ingestion-service` consumes live M1 candle streams, backfills gaps through
   broker-service, and writes expanded candles through `database-accessor-api`.
4. `database-accessor-api` reads and writes markets and candles in TimescaleDB.
5. `indicator-api` fetches candles from `database-accessor-api`, computes historical
   indicators, and can publish live indicator streams from Redis candle input.
6. `webserver` starts and stops broker or indicator streams, consumes Redis, and
   fans out WebSocket messages to frontend clients.
7. `frontend` fetches historical candles/indicators and applies live WebSocket
   updates to the chart.
8. `backtester` loads candle history through shared data access and runs selected
   strategy engines. Durable backtest run lifecycle and result records are stored
   through `database-accessor-api`.

## Data Contracts

- All service APIs use UTC epoch milliseconds for transport timestamps.
- Frontend chart points use `time` as epoch seconds only after converting from
  `timestamp_ms`.
- Redis stream names:
  - candles: `candles:{account_id}:{symbol}:{timeframe}`
  - ticks: `ticks:{account_id}:{symbol}`
  - indicators: `indicators:{account_id}:{exchange}:{symbol}:{timeframe}:{stream_id}`
- Timescale stores M1 candles in `candles`. Higher timeframe reads may use
  continuous aggregates or direct bucketing.
- Broker historical trendbar routes use cTrader-style query names `fromTs` and `toTs`.
- Database accessor routes use `start_ms` and `end_ms`.
- Durable backtest runs use `queued`, `running`, `succeeded`, and `failed`
  lifecycle states. Lifecycle timestamps are normalized storage fields; the
  complete immutable request is versioned JSON, and fills/trades are normalized
  child records. Request schema version 2 replaces legacy `allow_short` with
  explicit Allowed Directions. Result schema version 3 is the only accepted
  completed-result schema; closed trades carry nullable `stop_loss_price` and
  `take_profit_price` planned levels plus explicit trade direction so consumers
  do not infer long or short trades from fill order. Run history filters request
  attributes from that JSON document and returns matches by `submitted_at DESC`,
  then `run_id ASC`.
- Frontend and other non-storage consumers read durable backtest run history,
  fills, and trades through the public backtester API. `database-accessor-api`
  remains the primitive persistence API behind the backtester boundary.

## Change Guidance

- Treat this file as the canonical cross-service contract summary.
- When changing Candle, Tick, Timeframe, WebSocket, or storage behavior, use
  `docs/agent/CONTRACT-CHANGES.md` and `docs/CONTEXT-MAP.md` to find affected
  producer and consumer contexts.
- Keep implementation details in area contexts or reference docs; this file should
  stay small enough to read at agent startup.
