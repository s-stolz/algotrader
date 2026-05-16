# WebSocket Server

WebSocket server for streaming real-time market data from Redis to frontend clients.

## Overview

This WebSocket server acts as a bridge between Redis streams, broker-service,
indicator-api, and frontend clients. It manages subscriptions, controls source
stream lifecycle, and multiplexes live updates to connected clients.

## Architecture

```
Frontend (WebSocket Client)
    ↓
WebSocket Server (port 8765)
    ↓
├─→ Broker Service API (start/stop streams)
├─→ Indicator API (start/stop live indicator streams)
└─→ Redis Streams (consume live candles and indicators)
         ↑
    Broker Service / Indicator API (publish data)
```

## Features

- **WebSocket bridge** - WebSocket server plus lightweight health endpoint
- **Subscription Management** - Clients subscribe/unsubscribe to candle and indicator streams
- **Reference Counting** - Source streams start when first client subscribes and stop when last client unsubscribes
- **Redis Stream Consumption** - Consumes live candle and indicator streams
- **Graceful Shutdown** - Properly closes all connections and streams on SIGTERM/SIGINT

## Configuration

Configuration is centralized at the repository root.

```bash
cd ..
cp config/.env.secrets.example config/.env.secrets.local
python scripts/generate_env.py
cd webserver
```

Key settings:
- `WEBSERVER_WS_PORT` / `WEBSERVER_HEALTH_PORT`
- `BROKER_SERVICE_HOST` / `BROKER_SERVICE_PORT`
- `ACCOUNT_ID`
- `WEBSERVER_REDIS_BLOCK_MS` / `WEBSERVER_REDIS_BATCH_SIZE`
- `WEBSERVER_STREAM_QUEUE_SIZE` / `WEBSERVER_MAX_STREAM_LENGTH`

## Message Protocol

The current protocol uses flat JSON messages. The concise agent-facing summary
lives in `webserver/CONTEXT.md`.

Client-to-server examples:

```json
[
  {"type": "subscribeCandles", "symbol": "EURUSD", "timeframe": "M1"},
  {"type": "unsubscribeCandles", "symbol": "EURUSD", "timeframe": "M1"},
  {
    "type": "subscribeIndicator",
    "symbol": "EURUSD",
    "timeframe": "M1",
    "indicatorId": 1,
    "clientIndicatorId": "rsi-1"
  },
  {
    "type": "unsubscribeIndicator",
    "symbol": "EURUSD",
    "timeframe": "M1",
    "indicatorId": 1,
    "clientIndicatorId": "rsi-1"
  }
]
```

Server to client updates use flat message types such as `candleUpdate`,
`indicatorUpdate`, `indicatorSubscribed`, `indicatorUnsubscribed`, and `error`.
Timestamp and Redis payload rules are defined in the repository root
`CONTEXT.md`.

## Components

- `main.py`: process entrypoint, WebSocket server, health server, and message routing.
- `app/subscription_manager.py`: client subscriptions, source lifecycle, and fanout.
- `app/redis_consumer.py`: Redis stream consumption and payload expansion.
- `app/broker_client.py`: broker-service stream start/stop adapter.
- `app/indicator_api_client.py`: indicator-api live stream adapter.

## Running Locally

From the repository root:

```bash
cp config/.env.secrets.example config/.env.secrets.local
python scripts/generate_env.py
cd webserver
python main.py
```

## Running with Docker

```bash
make up
```

## Timeframes

Supported timeframe codes:
- `M1` - 1 minute
- `M5` - 5 minutes
- `M15` - 15 minutes
- `M30` - 30 minutes
- `H1` - 1 hour
- `H4` - 4 hours
- `D1` - 1 day

## Error Handling

- Invalid message format: Error response sent to client
- Missing required fields: Error response sent to client
- Broker-service unavailable: Error logged, subscription rolled back
- Redis connection lost: Automatic reconnection attempts
- Client disconnect: All subscriptions cleaned up, streams stopped if no other subscribers

## Development Notes

- The server maintains a single Redis connection for all stream consumption
- Each active stream runs its own consumption loop
- Broadcast logging is throttled (1% sample rate) to avoid spam
- All async operations have proper error handling
- Graceful shutdown ensures clean resource cleanup
