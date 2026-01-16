# Broker Service

Async broker microservice that talks to cTrader Open API, exposes FastAPI REST endpoints, and publishes market data/events into Redis Streams. This service runs locally (no Docker) for the first version and follows clean architecture guidance.

## High-level architecture

```
app/
  main.py
  settings.py
  api/
    routers/
      accounts.py
      orders.py
      positions.py
      deals.py
      market_data.py
      meta.py
    schemas.py
    dependencies.py
  application/
    interfaces.py
    services/
      account_service.py
      order_service.py
      trade_service.py (contains PositionService)
      market_data_service.py
  domain/
    value_objects.py
    models/
      account.py
      order.py
      trade.py
      position.py
      deal.py
      symbol.py
      tick.py
      trendbar.py
  infrastructure/
    ctrader_client.py
    ctrader_mappers.py
    ctrader_symbol_cache.py
    redis_streams_publisher.py
    stream_registry.py
    trendbar_stream_registry.py
    logging.py
    config.py
```

- **API Layer** – FastAPI routers with dependency injection, DTOs, and request/response schemas.
- **Application Layer** – Stateless services wired to abstract ports defined in `interfaces.py`.
- **Domain Layer** – Value objects and models describing accounts, orders, positions, deals, trades, ticks, and candles.
- **Infrastructure Layer** – Async wrappers for cTrader Open API, symbol caching, Redis Streams publishing, and dual-registry for tick and trendbar streaming.

## Key features

### Dual streaming registries
- **Tick streaming** (`StreamRegistry`) – Manages live tick subscriptions per symbol with configurable queue sizes and backpressure handling
- **Trendbar streaming** (`TrendbarStreamRegistry`) – Manages live candle/bar subscriptions with timeframe support and deduplication logic for completed bars

### Position and deal management
- **Positions** – View open positions and close them (full or partial close)
- **Deals** – Retrieve execution history with detailed close position information including PnL, commission, and swap

### Symbol management
- **Symbol caching** (`CtraderSymbolCache`) – Local cache of symbol metadata to reduce API calls
- **Symbol lookups** – Fast symbol info retrieval with support for both symbol names and IDs

### Configuration via Pydantic Settings
- Environment-based configuration with `.env` file support
- Separate credential loading for cTrader API
- Type-safe settings with validation

### Dependency injection
- `ServiceContainer` manages service lifecycle and wiring
- FastAPI dependency injection for clean separation of concerns
- Proper startup/shutdown lifecycle management

## Runtime overview

1. FastAPI boots via `app.main:create_app` and configures structured logging.
2. Startup event initializes `ServiceContainer` which wires together:
   - `CtraderClient` for broker communication
   - `RedisStreamsPublisher` for publishing to Redis
   - `StreamRegistry` for managing live tick streams
   - `TrendbarStreamRegistry` for managing live candle/trendbar streams
   - Application services (`AccountService`, `OrderService`, `PositionService`, `MarketDataService`)
3. Routers use dependency injection to access services via `app.state.container`.
4. Market data streaming:
   - Tick streams: Subscribe to symbol ticks, queue them, and fan-out to Redis stream `ticks:{account_id}:{symbol}`
   - Trendbar streams: Subscribe to live candles, deduplicate, and publish to Redis stream `candles:{account_id}:{symbol}:{timeframe}`
5. Shutdown stops all tick and trendbar streams, unsubscribes from cTrader, and closes Redis connections.
6. CLI entry point `broker-service` command (defined in `pyproject.toml`) launches Uvicorn server.

## Configuration knobs

Environment variables (dotenv compatible) control connectivity:

| Variable | Description | Default |
| --- | --- | --- |
| `BROKER_SERVICE_PORT` | HTTP port for FastAPI | `8050` |
| `CTRADER_CLIENT_ID` | cTrader API client ID | (required) |
| `CTRADER_SECRET` | cTrader API secret | (required) |
| `CTRADER_HOST_TYPE` | cTrader host type (`demo` or `live`) | (required) |
| `CTRADER_ACCESS_TOKEN` | cTrader OAuth access token | (required) |
| `BROKER_REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `BROKER_TICK_QUEUE_SIZE` | Per-symbol asyncio.Queue size | `1000` |
| `BROKER_TICK_STREAM_MAXLEN` | Redis stream MAXLEN for ticks (approximate) | `None` (unlimited) |
| `BROKER_CANDLE_STREAM_MAXLEN` | Redis stream MAXLEN for candles (approximate) | `None` (unlimited) |
| `BROKER_MAX_SYMBOL_STREAMS` | Safety cap for concurrent tick streams | `20` |
| `BROKER_MAX_TRENDBAR_STREAMS` | Safety cap for concurrent trendbar streams | `10` |
| `BROKER_LOG_LEVEL` | Logging level | `INFO` |
| `BROKER_CTRADER_REQUEST_TIMEOUT_SECONDS` | Timeout for cTrader API requests | `20.0` |

> **Note**: Most broker-specific variables use the `BROKER_` prefix, but cTrader credentials use `CTRADER_` prefix.

## Local development

1. Create a Python 3.10+ virtual environment and install the service in editable mode:

```bash
cd broker-service
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Copy `sample.env` to `.env` and fill in your cTrader credentials (`CTRADER_CLIENT_ID`, `CTRADER_SECRET`, `CTRADER_HOST_TYPE`, `CTRADER_ACCESS_TOKEN`).

3. Start the API using the CLI command or Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8050
```

4. Check health status at `GET http://localhost:8050/meta/health` and explore the API:
   - `/accounts` – List trading accounts
   - `/orders` – Manage orders (open, history, place, cancel)
   - `/positions` – View and close positions
   - `/deals` – Get deal (execution) history
   - `/symbols` – Symbol info, tick streams, trendbar streams, and historical candles

## Testing

> **Note**: No test suite currently exists. The project structure supports future testing following these guidelines:

When tests are added, install the development dependencies and run the layered pytest suite:

```bash
cd broker-service
pip install -e .[dev]
pytest              # run full suite with coverage
pytest test/unit    # run only unit layer
pytest -m integration  # run integration layer (no external services needed)
```

The test tree should mirror the `app/` structure so that every router, service, and infrastructure component has a dedicated home for its tests. Additional markers can be used for `contract`, `e2e`, and `slow` scenarios when introducing heavier checks.

### Available dev dependencies for testing:
- `pytest` – Test framework
- `pytest-asyncio` – Async test support
- `pytest-cov` – Coverage reporting
- `pytest-mock` – Mocking utilities
- `pytest-timeout` – Test timeout handling
- `httpx` – HTTP client for API testing
- `fakeredis[asyncio]` – Redis mock for testing
- `freezegun` – Time mocking utilities
