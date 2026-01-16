from __future__ import annotations

from typing import Any, cast

from redis.asyncio import Redis

from app.application.interfaces import RedisPublisherPort
from app.domain.models import Tick, Trendbar
from app.domain.value_objects import AccountId, Timeframe
from app.settings import Settings


class RedisStreamsPublisher(RedisPublisherPort):
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def publish_tick(self, tick: Tick, account_id: AccountId, symbol: str) -> None:
        key = f"ticks:{account_id}:{symbol}"
        payload = {
            "b": f"{tick.b:.{tick.digits}f}",
            "a": f"{tick.a:.{tick.digits}f}",
            "t": str(tick.t),
        }
        await self._xadd(key, payload, self._settings.tick_stream_maxlen)

    async def publish_candle(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        candle: Trendbar,
    ) -> None:
        key = f"candles:{account_id}:{symbol}:{timeframe.value}"
        d = candle.digits
        payload = {
            "o": f"{candle.o:.{d}f}",
            "h": f"{candle.h:.{d}f}",
            "l": f"{candle.l:.{d}f}",
            "c": f"{candle.c:.{d}f}",
            "v": str(candle.v),
            "t": str(candle.t),
        }
        await self._xadd(key, payload, self._settings.candle_stream_maxlen)

    async def publish_order_event(self, account_id: AccountId, event: dict) -> None:
        key = f"order-events:{account_id}"
        await self._xadd(key, self._stringify(event), None)

    async def publish_trade_event(self, account_id: AccountId, event: dict) -> None:
        key = f"trade-events:{account_id}"
        await self._xadd(key, self._stringify(event), None)

    async def _xadd(self, key: str, payload: dict[str, Any], max_len: int | None) -> None:
        kwargs = {}
        if max_len:
            kwargs["maxlen"] = max_len
            kwargs["approximate"] = True
        fields = cast(dict[str, str], self._stringify(payload))
        await self._redis.xadd(key, fields, **kwargs)  # type: ignore[arg-type]

    @staticmethod
    def _stringify(payload: dict[str, Any]) -> dict[str, str]:
        return {str(k): str(v) for k, v in payload.items()}

    async def close(self) -> None:
        await self._redis.close()
