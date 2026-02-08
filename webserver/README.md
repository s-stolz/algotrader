# WebSocket Server

WebSocket server for streaming real-time market data from Redis to frontend clients.

## Overview

This WebSocket server acts as a bridge between the broker-service/Redis streams and frontend clients. It manages subscriptions, controls stream lifecycle via the broker-service API, and multiplexes data to connected clients.

## Architecture

```
Frontend (WebSocket Client)
    ↓
WebSocket Server (port 8765)
    ↓
├─→ Broker Service API (start/stop streams)
└─→ Redis Streams (consume real-time data)
         ↑
    Broker Service (publishes data)
```

## Features

- **WebSocket-only** - No HTTP/Express overhead
- **Subscription Management** - Clients subscribe/unsubscribe to specific symbols and timeframes
- **Reference Counting** - Streams start when first client subscribes, stop when last client unsubscribes
- **Redis Stream Consumption** - Consumes from `candles:{account}:{symbol}:{timeframe}` and `ticks:{account}:{symbol}` streams
- **Graceful Shutdown** - Properly closes all connections and streams on SIGTERM/SIGINT

## Configuration

Copy `sample.env` to `.env` and configure:

```bash
# WebSocket Server
WS_PORT=8765

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Broker Service
BROKER_SERVICE_URL=http://broker-service:8050
ACCOUNT_ID=your_account_id_here

# Stream Settings
REDIS_BLOCK_MS=5000
REDIS_BATCH_SIZE=100
STREAM_QUEUE_SIZE=1000
MAX_STREAM_LENGTH=10000
```

## Message Protocol

The server uses a JSON-based message format compatible with the frontend's Ticket protocol:

```javascript
{
  "receiver": "Market",  // Message category
  "type": "SubscribeCandles",  // Message type
  "data": {  // Optional payload
    "symbol": "EURUSD",
    "timeframe": "M1"
  }
}
```

### Client → Server Messages

#### Login
```json
{
  "receiver": "Broker",
  "type": "Login"
}
```

#### Subscribe to Candles
```json
{
  "receiver": "Market",
  "type": "SubscribeCandles",
  "data": {
    "symbol": "EURUSD",
    "timeframe": "M1"
  }
}
```

#### Unsubscribe from Candles
```json
{
  "receiver": "Market",
  "type": "UnsubscribeCandles",
  "data": {
    "symbol": "EURUSD",
    "timeframe": "M1"
  }
}
```

#### Subscribe to Ticks
```json
{
  "receiver": "Market",
  "type": "SubscribeTicks",
  "data": {
    "symbol": "EURUSD"
  }
}
```

#### Unsubscribe from Ticks
```json
{
  "receiver": "Market",
  "type": "UnsubscribeTicks",
  "data": {
    "symbol": "EURUSD"
  }
}
```

### Server → Client Messages

#### Connection Established
```json
{
  "receiver": "System",
  "type": "Connected",
  "data": {
    "clientId": 1
  }
}
```

#### Login Success
```json
{
  "receiver": "System",
  "type": "LoginSuccess",
  "data": {
    "clientId": 1
  }
}
```

#### Subscription Confirmed
```json
{
  "receiver": "Market",
  "type": "SubscribedCandles",
  "data": {
    "symbol": "EURUSD",
    "timeframe": "M1"
  }
}
```

#### Candle Update
```json
{
  "receiver": "Market",
  "type": "CandleUpdate",
  "data": {
    "symbol": "EURUSD",
    "timeframe": "M1",
    "t": 1706371200000,  // Timestamp (ms)
    "o": 1.0850,         // Open
    "h": 1.0855,         // High
    "l": 1.0848,         // Low
    "c": 1.0852,         // Close
    "v": 125000          // Volume
  }
}
```

#### Tick Update
```json
{
  "receiver": "Market",
  "type": "TickUpdate",
  "data": {
    "symbol": "EURUSD",
    "t": 1706371234567,  // Timestamp (ms)
    "bid": 1.0850,       // Bid price
    "ask": 1.0852        // Ask price
  }
}
```

#### Error
```json
{
  "receiver": "System",
  "type": "Error",
  "data": {
    "error": "Error message"
  }
}
```

## Components

### server.js
Entry point that loads configuration and starts the WebSocket server.

### app/utils/websocketserver.js
WebSocket server initialization and message routing. Handles client connections and dispatches messages to appropriate handlers.

### app/subscriptionManager.js
Manages client subscriptions with reference counting. Coordinates stream lifecycle (start/stop) based on active subscriptions.

### app/redisConsumer.js
Consumes from Redis streams using `XREAD BLOCK` and broadcasts parsed data to subscribed clients.

### app/brokerClient.js
HTTP client for broker-service API. Starts/stops tick and trendbar streams via REST endpoints.

## Running Locally

```bash
# Install dependencies
npm install

# Set up environment
cp sample.env .env
# Edit .env with your configuration

# Run
npm start

# Development mode (with nodemon)
npx nodemon server.js
```

## Running with Docker

```bash
# From project root
docker-compose up webserver
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
