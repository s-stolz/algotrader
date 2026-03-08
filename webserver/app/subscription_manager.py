import json
import logging
from typing import TYPE_CHECKING, Dict, Set

from websockets.asyncio.server import ServerConnection

if TYPE_CHECKING:
    from app.broker_client import BrokerClient
    from app.redis_consumer import RedisConsumer

logger = logging.getLogger(__name__)


class SubscriptionManager:

    def __init__(
        self,
        broker_client: 'BrokerClient',
        redis_consumer: 'RedisConsumer'
    ):
        self.broker_client = broker_client
        self.redis_consumer = redis_consumer

        # Track subscriptions: clientId -> Set[subscriptionKey]
        self.client_subscriptions: Dict[int, Set[str]] = {}

        # Track reference counts: subscriptionKey -> count
        self.subscription_counts: Dict[str, int] = {}

        # Map clients to WebSocket instances: clientId -> ws
        self.clients: Dict[int, ServerConnection] = {}

        self.next_client_id = 1

    def register_client(self, ws: ServerConnection) -> int:
        client_id = self.next_client_id
        self.next_client_id += 1

        self.clients[client_id] = ws
        self.client_subscriptions[client_id] = set()

        return client_id

    async def unregister_client(self, client_id: int):
        subscriptions = self.client_subscriptions.get(client_id)
        if subscriptions:
            for sub_key in list(subscriptions):
                await self._decrement_subscription(sub_key)
            self.client_subscriptions.pop(client_id, None)

        self.clients.pop(client_id, None)

    async def subscribe_candles(
        self, client_id: int, symbol: str, timeframe: str
    ):
        timeframe_code = timeframe.upper()
        sub_key = f"candle:{symbol}:{timeframe_code}"

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None:
            raise ValueError(f"Client {client_id} not found")

        if sub_key in client_subs:
            return

        client_subs.add(sub_key)

        count = self.subscription_counts.get(sub_key, 0)
        self.subscription_counts[sub_key] = count + 1

        if count == 0:
            try:
                await self.broker_client.start_trendbar_stream(
                    symbol, timeframe_code
                )
                await self.redis_consumer.start_candle_stream(symbol, timeframe_code)

            except Exception:
                client_subs.discard(sub_key)
                self.subscription_counts[sub_key] = count
                raise

    async def unsubscribe_candles(
        self, client_id: int, symbol: str, timeframe: str
    ):
        sub_key = f"candle:{symbol}:{timeframe.upper()}"

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None or sub_key not in client_subs:
            return

        client_subs.discard(sub_key)
        await self._decrement_subscription(sub_key)

    async def _decrement_subscription(self, sub_key: str):
        count = self.subscription_counts.get(sub_key, 0)
        new_count = max(0, count - 1)

        if new_count == 0:
            self.subscription_counts.pop(sub_key, None)

            parts = sub_key.split(':')
            stream_type = parts[0]
            symbol = parts[1]
            timeframe = parts[2]
            try:
                if stream_type == 'candle':
                    stream_key = self.redis_consumer.get_candle_stream_key(symbol, timeframe)
                    self.redis_consumer.stop_stream(stream_key)

            except Exception as e:
                logger.error(f"Error stopping streams for {sub_key}: {e}")
        else:
            self.subscription_counts[sub_key] = new_count

    def broadcast_candle(self, symbol: str, timeframe: str, data: dict):
        sub_key = f"candle:{symbol}:{timeframe.upper()}"

        message = json.dumps({
            'type': 'candleUpdate',
            'symbol': symbol,
            'timeframe': timeframe,
            **data
        })

        self._broadcast(sub_key, message)

    def _broadcast(self, sub_key: str, message: str):
        import asyncio

        for client_id, subscriptions in self.client_subscriptions.items():
            ws = self.clients.get(client_id)

            if sub_key not in subscriptions or ws is None:
                continue

            try:
                asyncio.create_task(ws.send(message))
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
