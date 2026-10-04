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

The flat JSON subscription/update protocol is defined in
[service context](CONTEXT.md#contracts). Timestamp and Redis payload rules live in
[root context](../CONTEXT.md#shared-contracts).

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

Timeframe support depends on the upstream broker/indicator source and storage.
Use [contract-change guidance](../docs/agent/CONTRACT-CHANGES.md) when adding one.

## Error Handling

- Invalid message format: Error response sent to client
- Missing required fields: Error response sent to client
- Broker-service unavailable: Error logged, subscription rolled back
- Redis connection lost: Automatic reconnection attempts
- Client disconnect: All subscriptions cleaned up, streams stopped if no other subscribers
