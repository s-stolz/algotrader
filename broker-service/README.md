# Broker Service

Async broker microservice that talks to cTrader Open API, exposes FastAPI REST endpoints, and publishes market data/events into Redis Streams. Run it locally or through the repository Docker Compose stack.

## Architecture

For module ownership and change guidance, read [CONTEXT.md](CONTEXT.md).
Routes call application services through ports; infrastructure adapts cTrader
and Redis, while domain types carry broker concepts.

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

### Configuration via dataclass settings
- Process-environment configuration; Compose loads the generated env files
- Separate credential loading for cTrader API
- Typed parsing/validation in `app/settings.py`

### Dependency injection
- `ServiceContainer` manages service lifecycle and wiring
- FastAPI dependency injection for clean separation of concerns
- Proper startup/shutdown lifecycle management

## Market Data Contracts

Timestamp units, query bounds, and Redis stream shapes are defined in
[root context](../CONTEXT.md#shared-contracts).

## Runtime overview

1. FastAPI boots via `app.main:create_app` and configures structured logging.
2. Startup event initializes `ServiceContainer` which wires together:
   - `TokenLifecycleManager` for expiry-driven cTrader OAuth refresh
   - `RedisTokenRepository` for token state in Redis hash
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

Environment variables control connectivity. In this repository they are generated
under `config/` via `make config`; see [configuration context](../config/CONTEXT.md).

| Variable | Description | Default |
| --- | --- | --- |
| `BROKER_SERVICE_PORT` | HTTP port for FastAPI | `8080` |
| `CTRADER_CLIENT_ID` | cTrader API client ID | (required) |
| `CTRADER_SECRET` | cTrader API secret | (required) |
| `CTRADER_HOST_TYPE` | cTrader host type (`demo` or `live`) | (required) |
| `CTRADER_ACCESS_TOKEN` | cTrader OAuth access token | (required) |
| `CTRADER_REFRESH_TOKEN` | cTrader OAuth refresh token | (required) |
| `CTRADER_TOKEN_URL` | OAuth token refresh URL | `https://openapi.ctrader.com/apps/token` |
| `CTRADER_ACCESS_TOKEN_EXPIRES_IN_SECONDS` | Fallback TTL if refresh response omits `expires_in` | `2628000` |
| `CTRADER_TOKEN_REQUEST_TIMEOUT_SECONDS` | HTTP timeout for token refresh request | `10.0` |
| `BROKER_REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `BROKER_TOKEN_REDIS_KEY` | Redis hash key storing current OAuth token state | `broker:auth:ctrader:current` |
| `BROKER_TOKEN_REFRESH_EARLY_SECONDS` | Refresh lead time before expiry | `604800` |
| `BROKER_TOKEN_REFRESH_RETRY_DELAY_SECONDS` | Delay between refresh retries | `30` |
| `BROKER_TOKEN_REFRESH_MAX_RETRIES` | Max retry attempts per refresh cycle | `3` |
| `BROKER_TICK_QUEUE_SIZE` | Per-symbol asyncio.Queue size | `1000` |
| `BROKER_TICK_STREAM_MAXLEN` | Redis stream MAXLEN for ticks (approximate) | `None` (unlimited) |
| `BROKER_CANDLE_STREAM_MAXLEN` | Redis stream MAXLEN for candles (approximate) | `None` (unlimited) |
| `BROKER_MAX_SYMBOL_STREAMS` | Safety cap for concurrent tick streams | `20` |
| `BROKER_MAX_TRENDBAR_STREAMS` | Safety cap for concurrent trendbar streams | `10` |
| `BROKER_LOG_LEVEL` | Logging level | `INFO` |
| `BROKER_CTRADER_REQUEST_TIMEOUT_SECONDS` | Timeout for cTrader API requests | `20.0` |

> **Note**: Most broker-specific variables use the `BROKER_` prefix, but cTrader credentials use `CTRADER_` prefix.

## Local development

1. From the repository root, install the service and shared library dependencies:

```bash
make venv SERVICE=broker-service
```

2. From the repository root, create secrets and generate the environment:

```bash
cp config/.env.secrets.example config/.env.secrets.local
python scripts/generate_env.py
cd broker-service
```

3. For a direct host launch, supply the generated shared, runtime-secret, and
broker-secret variables to the process environment first. Configuration generation
does not load them. Set `BROKER_REDIS_URL` to the host-reachable Redis address.
Then start the API from `broker-service/`:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Alternatively, `make up-build` from the repository root loads configuration and
service networking through Compose.

4. Check health status at `GET http://localhost:8080/meta/health` and explore the API:
   - `/accounts` – List trading accounts
   - `/orders` – Manage orders (open, history, place, cancel)
   - `/positions` – View and close positions
   - `/deals` – Get deal (execution) history
   - `/symbols` – Symbol info, tick streams, trendbar streams, and historical candles

## Testing

The broker-service has a unittest suite under `tests/` and mirrors the `app/` structure.

Run all tests:

```bash
cd broker-service
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

Run via helper module:

```bash
cd broker-service
.venv/bin/python -m tests.run_tests
```

Run via the package entrypoint installed by `make venv SERVICE=broker-service`:

```bash
cd broker-service
.venv/bin/broker-service-test
```

## Local browser authorization

Register your own application at <https://openapi.ctrader.com/> and wait for
approval. Add the exact redirect URI `http://localhost:8080/redirect`; the
Playground redirect cannot be used by this command. Supply `CTRADER_CLIENT_ID`,
`CTRADER_SECRET`, and `CTRADER_HOST_TYPE` (`demo` or `live`) through a protected
environment file. Do not put credentials in command arguments.

The packaged installer invokes:

```sh
python -m app.onboarding authorize --scope accounts --output /config/broker.env --bind-address 0.0.0.0
```

Use an interactive container with `/config` mounted and publish only
`127.0.0.1:8080:8080`. The container bind override permits Docker forwarding;
without that override the command listens only on loopback. Choose `trading`
instead of `accounts` only to authorize broker orders. Open the printed local
link, authorize in cTrader, then select the displayed broker account in the
terminal. The command writes no tokens
to standard output. Missing or mismatched OAuth state rejects the callback before
code exchange. Retry from the setup link if that occurs; if cTrader repeatedly
omits state, browser onboarding cannot proceed securely. Its documentation does
not promise state echo, so test the complete flow with a real demo account before
claiming provider acceptance.

For reconnect, stop the broker service first while leaving Redis running. Add
`--expected-account-id EXISTING_ID --replace-token-state` and supply
`BROKER_REDIS_URL` on the installation's Compose network. Other accounts or
environments are rejected. The protected output includes `ACCOUNT_ID`, application
credentials, tokens, `CTRADER_ACCESS_TOKEN_ISSUED_AT`, and
`CTRADER_ACCESS_TOKEN_EXPIRES_AT`. Preserve these timestamps when generating the
runtime environment. If Redis communication fails after validation, retain the
protected output for recovery; do not start the broker until setup completes.

Protocol references: [application registration](https://help.ctrader.com/open-api/api-application/)
and [authorization and refresh](https://help.ctrader.com/open-api/account-authentication/).
