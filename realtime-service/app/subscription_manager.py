from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from db_accessor_client.market_sources import BrokerMarketResolver
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
        market_resolver: BrokerMarketResolver,
    ):
        self.broker_client = broker_client
        self.redis_consumer = redis_consumer
        self.indicator_api_client = indicator_api_client
        self.market_resolver = market_resolver
        self.client_subscriptions: dict[int, set[str]] = {}
        self.subscription_counts: dict[str, int] = {}
        self.clients: dict[int, ServerConnection] = {}
        self.client_indicator_bindings: dict[int, dict[str, str]] = {}
        self.candle_meta_by_sub_key: dict[str, dict] = {}
        self.indicator_meta_by_sub_key: dict[str, dict] = {}
        self.indicator_sub_key_by_stream_id: dict[str, str] = {}
        self.source_dependency_counts: dict[str, int] = {}
        self._subscription_lock = asyncio.Lock()
        self.next_client_id = 1

    def register_client(self, ws: ServerConnection) -> int:
        client_id = self.next_client_id
        self.next_client_id += 1
        self.clients[client_id] = ws
        self.client_subscriptions[client_id] = set()
        self.client_indicator_bindings[client_id] = {}
        return client_id

    async def unregister_client(self, client_id: int):
        for sub_key in list(self.client_subscriptions.get(client_id, set())):
            if sub_key in self.candle_meta_by_sub_key:
                meta = self.candle_meta_by_sub_key[sub_key]
                await self.unsubscribe_candles(client_id, meta["market_id"], meta["timeframe"])
            elif sub_key in self.indicator_meta_by_sub_key:
                meta = self.indicator_meta_by_sub_key[sub_key]
                await self.unsubscribe_indicator(
                    client_id=client_id,
                    market_id=meta["market_id"],
                    timeframe=meta["timeframe"],
                    indicator_id=meta["indicator_id"],
                    parameters=meta["parameters"],
                )
        self.client_subscriptions.pop(client_id, None)
        self.client_indicator_bindings.pop(client_id, None)
        self.clients.pop(client_id, None)

    async def subscribe_candles(self, client_id: int, market_id: int, timeframe: str):
        market = await self.market_resolver.resolve(market_id)
        symbol = market["symbol"].upper()
        timeframe = timeframe.upper()
        sub_key = self._make_candle_sub_key(market_id, timeframe)
        async with self._subscription_lock:
            client_subs = self._client_subscriptions(client_id)
            if sub_key in client_subs:
                return
            await self._increment_source_dependency(market, timeframe)
            count = self.subscription_counts.get(sub_key, 0)
            try:
                if count == 0:
                    await self.redis_consumer.start_candle_stream(symbol, timeframe)
            except Exception:
                await self._decrement_source_dependency(market, timeframe)
                raise
            self.candle_meta_by_sub_key[sub_key] = {
                "market_id": market_id,
                "broker_symbol_id": market["broker_symbol_id"],
                "symbol": symbol,
                "timeframe": timeframe,
            }
            client_subs.add(sub_key)
            self.subscription_counts[sub_key] = count + 1

    async def unsubscribe_candles(self, client_id: int, market_id: int, timeframe: str):
        sub_key = self._make_candle_sub_key(market_id, timeframe.upper())
        async with self._subscription_lock:
            client_subs = self.client_subscriptions.get(client_id, set())
            if sub_key not in client_subs:
                return
            client_subs.remove(sub_key)
            meta = self.candle_meta_by_sub_key[sub_key]
            remaining = self.subscription_counts[sub_key] - 1
            if remaining:
                self.subscription_counts[sub_key] = remaining
            else:
                self.subscription_counts.pop(sub_key)
                self.candle_meta_by_sub_key.pop(sub_key)
                if not any(
                    other["symbol"] == meta["symbol"] and other["timeframe"] == meta["timeframe"]
                    for other in self.candle_meta_by_sub_key.values()
                ):
                    self.redis_consumer.stop_stream(
                        self.redis_consumer.get_candle_stream_key(meta["symbol"], meta["timeframe"])
                    )
            await self._decrement_source_dependency(meta, meta["timeframe"])

    async def subscribe_indicator(
        self,
        *,
        client_id: int,
        market_id: int,
        timeframe: str,
        indicator_id: int,
        parameters: dict | None,
        client_indicator_id: str,
    ) -> dict:
        market = await self.market_resolver.resolve(market_id)
        symbol = market["symbol"].upper()
        exchange = market["exchange"]
        timeframe = timeframe.upper()
        params = parameters or {}
        sub_key = self._make_indicator_sub_key(market_id, timeframe, indicator_id, params)
        metadata = await self.indicator_api_client.get_indicator_metadata(indicator_id)
        if not metadata.get("supports_live", True):
            raise ValueError("Indicator does not support live streaming")
        sources = await self.market_resolver.dependencies(market, metadata.get("inputs") or [])
        async with self._subscription_lock:
            client_subs = self._client_subscriptions(client_id)
            meta = self.indicator_meta_by_sub_key.get(sub_key)
            if meta is not None and [
                (source["symbol_id"], source["broker_symbol_id"]) for source in sources
            ] != [(source["symbol_id"], source["broker_symbol_id"]) for source in meta["sources"]]:
                raise ValueError("Live indicator inputs changed; reopen the subscription")
            if sub_key in client_subs:
                self.client_indicator_bindings[client_id][sub_key] = client_indicator_id
                return {
                    "stream_id": self.indicator_meta_by_sub_key[sub_key]["stream_id"],
                    "already_subscribed": True,
                }
            acquired = []
            started = None
            try:
                for source in sources:
                    await self._increment_source_dependency(source, timeframe)
                    acquired.append(source)
                if meta is None:
                    started = await self.indicator_api_client.start_live_indicator_stream(
                        market_id=market_id,
                        symbol=symbol,
                        timeframe=timeframe,
                        indicator_id=indicator_id,
                        parameters=params,
                        exchange=exchange,
                    )
                    await self.redis_consumer.start_indicator_stream(
                        stream_key=started["redis_stream_key"], stream_id=started["stream_id"]
                    )
                    meta = {
                        "market_id": market_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "exchange": exchange,
                        "indicator_id": indicator_id,
                        "parameters": params,
                        "sources": sources,
                        "stream_id": started["stream_id"],
                        "redis_stream_key": started["redis_stream_key"],
                    }
                    self.indicator_meta_by_sub_key[sub_key] = meta
                    self.indicator_sub_key_by_stream_id[meta["stream_id"]] = sub_key
            except Exception:
                if started is not None:
                    self.redis_consumer.stop_stream(started["redis_stream_key"])
                    try:
                        await self.indicator_api_client.stop_live_indicator_stream(
                            market_id=market_id,
                            symbol=symbol,
                            timeframe=timeframe,
                            indicator_id=indicator_id,
                            parameters=params,
                            exchange=exchange,
                        )
                    except Exception:
                        logger.exception("Could not roll back indicator stream")
                for source in reversed(acquired):
                    await self._decrement_source_dependency(source, timeframe)
                raise
            client_subs.add(sub_key)
            self.subscription_counts[sub_key] = self.subscription_counts.get(sub_key, 0) + 1
            self.client_indicator_bindings[client_id][sub_key] = client_indicator_id
            return {"stream_id": meta["stream_id"], "already_subscribed": False}

    async def unsubscribe_indicator(
        self,
        *,
        client_id: int,
        market_id: int,
        timeframe: str,
        indicator_id: int,
        parameters: dict | None,
    ) -> None:
        sub_key = self._make_indicator_sub_key(
            market_id, timeframe.upper(), indicator_id, parameters or {}
        )
        async with self._subscription_lock:
            client_subs = self.client_subscriptions.get(client_id, set())
            if sub_key not in client_subs:
                return
            client_subs.remove(sub_key)
            self.client_indicator_bindings[client_id].pop(sub_key, None)
            meta = self.indicator_meta_by_sub_key[sub_key]
            for source in meta["sources"]:
                await self._decrement_source_dependency(source, meta["timeframe"])
            remaining = self.subscription_counts[sub_key] - 1
            if remaining:
                self.subscription_counts[sub_key] = remaining
                return
            self.subscription_counts.pop(sub_key)
            self.indicator_meta_by_sub_key.pop(sub_key)
            self.indicator_sub_key_by_stream_id.pop(meta["stream_id"], None)
            self.redis_consumer.stop_stream(meta["redis_stream_key"])
            try:
                await self.indicator_api_client.stop_live_indicator_stream(
                    market_id=meta["market_id"],
                    symbol=meta["symbol"],
                    timeframe=meta["timeframe"],
                    indicator_id=meta["indicator_id"],
                    parameters=meta["parameters"],
                    exchange=meta["exchange"],
                )
            except Exception:
                logger.exception("Failed to stop indicator stream %s", meta["stream_id"])

    def _client_subscriptions(self, client_id: int) -> set[str]:
        subscriptions = self.client_subscriptions.get(client_id)
        if subscriptions is None:
            raise ValueError(f"Client {client_id} not found")
        return subscriptions

    async def _increment_source_dependency(self, market: dict, timeframe: str) -> None:
        symbol = market["symbol"].upper()
        expected_symbol_id = market["broker_symbol_id"]
        source_key = self._make_source_key(symbol, timeframe, expected_symbol_id)
        count = self.source_dependency_counts.get(source_key, 0)
        if count == 0:
            await self.broker_client.start_trendbar_stream(
                symbol, timeframe, expected_symbol_id=expected_symbol_id
            )
        self.source_dependency_counts[source_key] = count + 1

    async def _decrement_source_dependency(self, market: dict, timeframe: str) -> None:
        symbol = market["symbol"].upper()
        expected_symbol_id = market["broker_symbol_id"]
        source_key = self._make_source_key(symbol, timeframe, expected_symbol_id)
        count = self.source_dependency_counts.get(source_key, 0)
        if count > 1:
            self.source_dependency_counts[source_key] = count - 1
        elif count == 1:
            self.source_dependency_counts.pop(source_key)
            try:
                await self.broker_client.stop_trendbar_stream(
                    symbol, timeframe, expected_symbol_id=expected_symbol_id
                )
            except Exception:
                logger.exception("Failed stopping trendbar stream for %s %s", symbol, timeframe)

    def broadcast_candle(self, symbol: str, timeframe: str, data: dict):
        for sub_key, meta in self.candle_meta_by_sub_key.items():
            if meta["symbol"] == symbol.upper() and meta["timeframe"] == timeframe.upper():
                self._broadcast(
                    sub_key,
                    json.dumps(
                        {
                            **data,
                            "type": "candleUpdate",
                            "market_id": meta["market_id"],
                            "symbol": meta["symbol"],
                            "timeframe": meta["timeframe"],
                        }
                    ),
                )

    def broadcast_indicator(self, stream_id: str, data: dict):
        sub_key = self.indicator_sub_key_by_stream_id.get(stream_id)
        meta = self.indicator_meta_by_sub_key.get(sub_key or "")
        if not meta:
            return
        for client_id, subscriptions in self.client_subscriptions.items():
            if sub_key not in subscriptions:
                continue
            client_indicator_id = self.client_indicator_bindings[client_id].get(sub_key)
            ws = self.clients.get(client_id)
            if ws is not None and client_indicator_id:
                asyncio.create_task(
                    self._send(
                        ws,
                        json.dumps(
                            {
                                "type": "indicatorUpdate",
                                "market_id": meta["market_id"],
                                "clientIndicatorId": client_indicator_id,
                                "streamId": stream_id,
                                "symbol": meta["symbol"],
                                "timeframe": meta["timeframe"],
                                "indicatorId": meta["indicator_id"],
                                "timestamp_ms": data.get("timestamp_ms"),
                                "values": data.get("values", {}),
                                **({"replay": True} if data.get("replay") is True else {}),
                            }
                        ),
                    )
                )

    def _broadcast(self, sub_key: str, message: str):
        for client_id, subscriptions in self.client_subscriptions.items():
            ws = self.clients.get(client_id)
            if sub_key in subscriptions and ws is not None:
                asyncio.create_task(self._send(ws, message))

    @staticmethod
    async def _send(ws: ServerConnection, message: str):
        try:
            await ws.send(message)
        except Exception:
            logger.debug("Client disconnected during live fanout", exc_info=True)

    @staticmethod
    def _make_candle_sub_key(market_id: int, timeframe: str) -> str:
        return f"candle:{market_id}:{timeframe}"

    @staticmethod
    def _make_source_key(symbol: str, timeframe: str, broker_symbol_id: int) -> str:
        return f"source:{broker_symbol_id}:{symbol}:{timeframe}"

    @staticmethod
    def _make_indicator_sub_key(
        market_id: int, timeframe: str, indicator_id: int, parameters: dict[str, Any]
    ) -> str:
        encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        params_hash = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:12]
        return f"indicator:{market_id}:{timeframe}:{indicator_id}:{params_hash}"
