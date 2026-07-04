import asyncio
import inspect
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from app.subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)


class RedisConsumer:
    def __init__(
        self,
        redis_host: str,
        redis_port: int,
        account_id: str,
        block_ms: int = 5000,
        batch_size: int = 100,
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.account_id = account_id
        self.block_ms = block_ms
        self.batch_size = batch_size

        self.redis: Optional[aioredis.Redis] = None
        self.subscription_manager: Optional[SubscriptionManager] = None

        self.active_streams: Dict[str, dict] = {}
        self.is_connected = False

    @staticmethod
    def _redis_socket_timeout_seconds(block_ms: int) -> float | None:
        if block_ms <= 0:
            return None
        return (block_ms / 1000.0) + 1.0

    async def connect(self):
        try:
            self.redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                decode_responses=True,
                socket_timeout=self._redis_socket_timeout_seconds(self.block_ms),
            )
            ping_result = self.redis.ping()
            if inspect.isawaitable(ping_result):
                await ping_result
            self.is_connected = True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        self.is_connected = False

        for _, stream_info in list(self.active_streams.items()):
            stream_info["running"] = False
            if "task" in stream_info:
                stream_info["task"].cancel()
                try:
                    await stream_info["task"]
                except asyncio.CancelledError:
                    pass

        self.active_streams.clear()

        if self.redis:
            await self.redis.close()

    def get_candle_stream_key(self, symbol: str, timeframe: str) -> str:
        return f"candles:{self.account_id}:{symbol}:{timeframe}"

    async def start_candle_stream(self, symbol: str, timeframe: str):
        stream_key = self.get_candle_stream_key(symbol, timeframe)

        if stream_key in self.active_streams:
            return

        stream_info = {
            "last_id": "$",
            "running": True,
            "type": "candle",
            "symbol": symbol,
            "timeframe": timeframe,
        }

        self.active_streams[stream_key] = stream_info
        stream_info["task"] = asyncio.create_task(self._consume_stream(stream_key, stream_info))

    async def start_indicator_stream(self, stream_key: str, stream_id: str):
        if stream_key in self.active_streams:
            return

        stream_info = {
            "last_id": "$",
            "running": True,
            "type": "indicator",
            "stream_id": stream_id,
        }

        self.active_streams[stream_key] = stream_info
        stream_info["task"] = asyncio.create_task(self._consume_stream(stream_key, stream_info))

    def stop_stream(self, stream_key: str):
        stream_info = self.active_streams.get(stream_key)
        if stream_info:
            stream_info["running"] = False
            if "task" in stream_info:
                stream_info["task"].cancel()
            self.active_streams.pop(stream_key, None)

    async def _consume_stream(self, stream_key: str, stream_info: dict):
        while stream_info["running"] and self.is_connected:
            if not self.redis:
                return
            try:
                results = await self._read_stream_results(stream_key, stream_info)
            except asyncio.CancelledError:
                return
            if not results:
                continue
            self._dispatch_stream_results(stream_info, results)

    async def _read_stream_results(self, stream_key: str, stream_info: dict):
        assert self.redis is not None
        try:
            return await self.redis.xread(
                {stream_key: stream_info["last_id"]},
                count=self.batch_size,
                block=self.block_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if stream_info["running"]:
                logger.error(f"Error consuming stream {stream_key}: {e}")
                await asyncio.sleep(1)
            return None

    def _dispatch_stream_results(self, stream_info: dict, results: Any) -> None:
        for _, messages in results:
            for message_id, fields in messages:
                stream_info["last_id"] = message_id
                self._dispatch_stream_message(stream_info, fields)

    def _dispatch_stream_message(self, stream_info: dict, fields: Dict[str, str]) -> None:
        if not self.subscription_manager:
            return
        if stream_info["type"] == "candle":
            data = self._parse_candle_message(fields)
            self.subscription_manager.broadcast_candle(
                stream_info["symbol"],
                stream_info["timeframe"],
                data,
            )
            return
        if stream_info["type"] == "indicator":
            data = self._parse_indicator_message(fields)
            self.subscription_manager.broadcast_indicator(stream_info["stream_id"], data)

    def _parse_candle_message(self, fields: Dict[str, str]) -> Dict[str, Any]:
        data = {}
        numeric_fields = {"t", "o", "h", "l", "c", "v"}

        for key, value in fields.items():
            if key in numeric_fields:
                if key == "t":
                    data["timestamp_ms"] = int(value)
                elif key == "o":
                    data["open"] = float(value)
                elif key == "h":
                    data["high"] = float(value)
                elif key == "l":
                    data["low"] = float(value)
                elif key == "c":
                    data["close"] = float(value)
                elif key == "v":
                    data["volume"] = float(value)
            else:
                data[key] = value

        return data

    def _parse_indicator_message(self, fields: Dict[str, str]) -> Dict[str, Any]:
        values = {}
        raw_values = fields.get("d")
        if raw_values:
            try:
                parsed = json.loads(raw_values)
                if isinstance(parsed, dict):
                    values = parsed
            except json.JSONDecodeError:
                values = {}

        timestamp_ms = None
        raw_t = fields.get("t")
        if raw_t is not None:
            try:
                timestamp_ms = int(raw_t)
            except ValueError:
                timestamp_ms = None

        return {
            "timestamp_ms": timestamp_ms,
            "values": values,
        }
