from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

from websockets.asyncio.server import ServerConnection

if TYPE_CHECKING:
    from app.broker_client import BrokerClient
    from app.indicator_api_client import IndicatorApiClient
    from app.redis_consumer import RedisConsumer

logger = logging.getLogger(__name__)


class SubscriptionManager:
    def __init__(
        self,
        broker_client: BrokerClient,
        redis_consumer: RedisConsumer,
        indicator_api_client: IndicatorApiClient,
    ):
        self.broker_client = broker_client
        self.redis_consumer = redis_consumer
        self.indicator_api_client = indicator_api_client

        self.client_subscriptions: Dict[int, Set[str]] = {}
        self.subscription_counts: Dict[str, int] = {}
        self.clients: Dict[int, ServerConnection] = {}
        self.client_indicator_bindings: Dict[int, Dict[str, str]] = {}

        self.indicator_meta_by_sub_key: Dict[str, dict] = {}
        self.indicator_sub_key_by_stream_id: Dict[str, str] = {}

        self.source_dependency_counts: Dict[str, int] = {}

        self.next_client_id = 1

    def register_client(self, ws: ServerConnection) -> int:
        client_id = self.next_client_id
        self.next_client_id += 1

        self.clients[client_id] = ws
        self.client_subscriptions[client_id] = set()
        self.client_indicator_bindings[client_id] = {}
        return client_id

    async def unregister_client(self, client_id: int):
        subscriptions = self.client_subscriptions.get(client_id)
        bindings = self.client_indicator_bindings.get(client_id, {})

        if subscriptions:
            for sub_key in list(subscriptions):
                if sub_key.startswith("candle:"):
                    _, symbol, timeframe = sub_key.split(":", 2)
                    await self.unsubscribe_candles(client_id, symbol, timeframe)
                elif sub_key.startswith("indicator:"):
                    _, symbol, timeframe, exchange_key, indicator_id_str, _ = sub_key.split(":", 5)
                    exchange = None if exchange_key == "NA" else exchange_key
                    client_indicator_id = bindings.get(sub_key)
                    meta = self.indicator_meta_by_sub_key.get(sub_key)
                    await self.unsubscribe_indicator(
                        client_id=client_id,
                        symbol=symbol,
                        timeframe=timeframe,
                        indicator_id=int(indicator_id_str),
                        parameters=meta.get("parameters") if meta else {},
                        exchange=exchange,
                        client_indicator_id=client_indicator_id,
                    )

        self.client_subscriptions.pop(client_id, None)
        self.client_indicator_bindings.pop(client_id, None)
        self.clients.pop(client_id, None)

    async def subscribe_candles(self, client_id: int, symbol: str, timeframe: str):
        timeframe_code = timeframe.upper()
        symbol_code = symbol.upper()
        sub_key = self._make_candle_sub_key(symbol_code, timeframe_code)

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None:
            raise ValueError(f"Client {client_id} not found")

        if sub_key in client_subs:
            return

        await self._increment_source_dependency(symbol_code, timeframe_code)

        client_subs.add(sub_key)
        count = self.subscription_counts.get(sub_key, 0)
        self.subscription_counts[sub_key] = count + 1

        if count == 0:
            try:
                await self.redis_consumer.start_candle_stream(symbol_code, timeframe_code)
            except Exception:
                client_subs.discard(sub_key)
                self.subscription_counts[sub_key] = count
                await self._decrement_source_dependency(symbol_code, timeframe_code)
                raise

    async def unsubscribe_candles(self, client_id: int, symbol: str, timeframe: str):
        symbol_code = symbol.upper()
        timeframe_code = timeframe.upper()
        sub_key = self._make_candle_sub_key(symbol_code, timeframe_code)

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None or sub_key not in client_subs:
            return

        client_subs.discard(sub_key)
        await self._decrement_subscription(sub_key)
        await self._decrement_source_dependency(symbol_code, timeframe_code)

    async def subscribe_indicator(
        self,
        *,
        client_id: int,
        symbol: str,
        timeframe: str,
        indicator_id: int,
        parameters: Optional[dict],
        exchange: Optional[str],
        client_indicator_id: str,
    ) -> dict:
        symbol_code = symbol.upper()
        timeframe_code = timeframe.upper()
        params = parameters or {}
        params_hash = self._hash_params(params)
        sub_key = self._make_indicator_sub_key(
            symbol=symbol_code,
            timeframe=timeframe_code,
            exchange=exchange,
            indicator_id=indicator_id,
            params_hash=params_hash,
        )

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None:
            raise ValueError(f"Client {client_id} not found")

        if sub_key in client_subs:
            self.client_indicator_bindings[client_id][sub_key] = client_indicator_id
            meta = self.indicator_meta_by_sub_key.get(sub_key)
            return {
                "stream_id": meta.get("stream_id") if meta else None,
                "sub_key": sub_key,
                "already_subscribed": True,
            }

        await self._increment_source_dependency(symbol_code, timeframe_code)

        count = self.subscription_counts.get(sub_key, 0)
        self.subscription_counts[sub_key] = count + 1

        if count == 0:
            await self._start_indicator_stream_for_subscription(
                sub_key=sub_key,
                count=count,
                symbol_code=symbol_code,
                timeframe_code=timeframe_code,
                indicator_id=indicator_id,
                params=params,
                exchange=exchange,
            )

        client_subs.add(sub_key)
        self.client_indicator_bindings[client_id][sub_key] = client_indicator_id
        meta = self.indicator_meta_by_sub_key[sub_key]
        return {
            "stream_id": meta["stream_id"],
            "sub_key": sub_key,
            "already_subscribed": False,
        }

    async def unsubscribe_indicator(
        self,
        *,
        client_id: int,
        symbol: str,
        timeframe: str,
        indicator_id: int,
        parameters: Optional[dict],
        exchange: Optional[str],
        client_indicator_id: Optional[str] = None,
    ) -> None:
        symbol_code = symbol.upper()
        timeframe_code = timeframe.upper()
        params_hash = self._hash_params(parameters or {})
        sub_key = self._make_indicator_sub_key(
            symbol=symbol_code,
            timeframe=timeframe_code,
            exchange=exchange,
            indicator_id=indicator_id,
            params_hash=params_hash,
        )

        client_subs = self.client_subscriptions.get(client_id)
        if client_subs is None or sub_key not in client_subs:
            return

        client_subs.discard(sub_key)
        self.client_indicator_bindings.get(client_id, {}).pop(sub_key, None)

        await self._decrement_subscription(sub_key)
        await self._decrement_source_dependency(symbol_code, timeframe_code)

        if sub_key in self.subscription_counts:
            return

        meta = self.indicator_meta_by_sub_key.pop(sub_key, None)
        if not meta:
            return

        stream_id = meta.get("stream_id")
        if stream_id:
            self.indicator_sub_key_by_stream_id.pop(stream_id, None)

        redis_stream_key = meta.get("redis_stream_key")
        if redis_stream_key:
            self.redis_consumer.stop_stream(redis_stream_key)

        try:
            await self.indicator_api_client.stop_live_indicator_stream(
                symbol=symbol_code,
                timeframe=timeframe_code,
                indicator_id=indicator_id,
                parameters=meta.get("parameters", parameters or {}),
                exchange=exchange,
            )
            logger.info(
                "Stopped indicator stream: symbol=%s timeframe=%s indicator=%s stream_id=%s",
                symbol_code,
                timeframe_code,
                indicator_id,
                stream_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to stop indicator stream for %s %s indicator=%s: %s",
                symbol_code,
                timeframe_code,
                indicator_id,
                exc,
            )

    async def _start_indicator_stream_for_subscription(
        self,
        *,
        sub_key: str,
        count: int,
        symbol_code: str,
        timeframe_code: str,
        indicator_id: int,
        params: dict[str, Any],
        exchange: Optional[str],
    ) -> None:
        try:
            start_data = await self.indicator_api_client.start_live_indicator_stream(
                symbol=symbol_code,
                timeframe=timeframe_code,
                indicator_id=indicator_id,
                parameters=params,
                exchange=exchange,
            )
            redis_stream_key = start_data["redis_stream_key"]
            stream_id = start_data["stream_id"]
            self.indicator_meta_by_sub_key[sub_key] = {
                "symbol": symbol_code,
                "timeframe": timeframe_code,
                "indicator_id": indicator_id,
                "parameters": params,
                "exchange": exchange,
                "redis_stream_key": redis_stream_key,
                "stream_id": stream_id,
            }
            self.indicator_sub_key_by_stream_id[stream_id] = sub_key
            await self.redis_consumer.start_indicator_stream(
                stream_key=redis_stream_key,
                stream_id=stream_id,
            )
            logger.info(
                "Started indicator stream: symbol=%s timeframe=%s indicator=%s stream_id=%s",
                symbol_code,
                timeframe_code,
                indicator_id,
                stream_id,
            )
        except Exception:
            meta = self.indicator_meta_by_sub_key.pop(sub_key, None)
            if meta and meta.get("stream_id"):
                self.indicator_sub_key_by_stream_id.pop(meta["stream_id"], None)
                try:
                    await self.indicator_api_client.stop_live_indicator_stream(
                        symbol=symbol_code,
                        timeframe=timeframe_code,
                        indicator_id=indicator_id,
                        parameters=params,
                        exchange=exchange,
                    )
                except Exception:
                    pass
            self.subscription_counts[sub_key] = count
            if count == 0:
                self.subscription_counts.pop(sub_key, None)
            await self._decrement_source_dependency(symbol_code, timeframe_code)
            raise

    async def _increment_source_dependency(self, symbol: str, timeframe: str) -> None:
        source_key = self._make_source_key(symbol, timeframe)
        count = self.source_dependency_counts.get(source_key, 0)
        self.source_dependency_counts[source_key] = count + 1
        if count == 0:
            try:
                await self.broker_client.start_trendbar_stream(symbol, timeframe)
            except Exception:
                self.source_dependency_counts[source_key] = 0
                self.source_dependency_counts.pop(source_key, None)
                raise

    async def _decrement_source_dependency(self, symbol: str, timeframe: str) -> None:
        source_key = self._make_source_key(symbol, timeframe)
        count = self.source_dependency_counts.get(source_key, 0)
        new_count = max(0, count - 1)

        if new_count == 0:
            self.source_dependency_counts.pop(source_key, None)
            try:
                await self.broker_client.stop_trendbar_stream(symbol, timeframe)
            except Exception as exc:
                logger.error(
                    "Failed stopping trendbar stream for %s %s: %s",
                    symbol,
                    timeframe,
                    exc,
                )
        else:
            self.source_dependency_counts[source_key] = new_count

    async def _decrement_subscription(self, sub_key: str):
        count = self.subscription_counts.get(sub_key, 0)
        new_count = max(0, count - 1)
        if new_count == 0:
            self.subscription_counts.pop(sub_key, None)
            if sub_key.startswith("candle:"):
                _, symbol, timeframe = sub_key.split(":", 2)
                stream_key = self.redis_consumer.get_candle_stream_key(symbol, timeframe)
                self.redis_consumer.stop_stream(stream_key)
        else:
            self.subscription_counts[sub_key] = new_count

    def broadcast_candle(self, symbol: str, timeframe: str, data: dict):
        sub_key = self._make_candle_sub_key(symbol.upper(), timeframe.upper())
        message = json.dumps(
            {
                "type": "candleUpdate",
                "symbol": symbol,
                "timeframe": timeframe,
                **data,
            }
        )
        self._broadcast(sub_key, message)

    def broadcast_indicator(self, stream_id: str, data: dict):
        sub_key = self.indicator_sub_key_by_stream_id.get(stream_id)
        if not sub_key:
            return

        meta = self.indicator_meta_by_sub_key.get(sub_key)
        if not meta:
            return

        import asyncio

        for client_id, subscriptions in self.client_subscriptions.items():
            if sub_key not in subscriptions:
                continue

            ws = self.clients.get(client_id)
            if ws is None:
                continue

            client_indicator_id = self.client_indicator_bindings.get(client_id, {}).get(sub_key)
            if not client_indicator_id:
                continue

            message = {
                "type": "indicatorUpdate",
                "clientIndicatorId": client_indicator_id,
                "streamId": stream_id,
                "symbol": meta["symbol"],
                "timeframe": meta["timeframe"],
                "indicatorId": meta["indicator_id"],
                "timestamp_ms": data.get("timestamp_ms"),
                "values": data.get("values", {}),
            }
            try:
                asyncio.create_task(ws.send(json.dumps(message)))
            except Exception as exc:
                logger.error("Error sending indicator update to client %s: %s", client_id, exc)

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

    @staticmethod
    def _make_candle_sub_key(symbol: str, timeframe: str) -> str:
        return f"candle:{symbol}:{timeframe}"

    @staticmethod
    def _make_source_key(symbol: str, timeframe: str) -> str:
        return f"source:{symbol}:{timeframe}"

    @staticmethod
    def _hash_params(parameters: dict[str, Any]) -> str:
        encoded = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _make_indicator_sub_key(
        *,
        symbol: str,
        timeframe: str,
        exchange: Optional[str],
        indicator_id: int,
        params_hash: str,
    ) -> str:
        exchange_key = (exchange or "NA").upper()
        return f"indicator:{symbol}:{timeframe}:{exchange_key}:{indicator_id}:{params_hash}"
