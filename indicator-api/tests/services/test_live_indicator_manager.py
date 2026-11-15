import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

import pandas as pd
from app.schemas_live import LiveIndicatorStreamRequest
from app.services.candle_cache import CandleCache
from app.services.live_indicator_manager import LiveIndicatorManager

from tests.live_market_fixtures import live_market_resolver


class LiveCandleCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_opening_range_rejects_live_streaming_without_daily_history(self):
        manager = LiveIndicatorManager(CandleCache(), live_market_resolver())
        request = LiveIndicatorStreamRequest(
            market_id=1,
            account_id="123",
            symbol="TEST",
            timeframe="M5",
            indicator_id=7,
            parameters={},
        )
        with self.assertRaisesRegex(ValueError, "opening_range is not supported"):
            await manager.start_stream(request)

    async def test_live_indicator_values_ignore_continuity_without_exposing_metadata(self):
        cache = CandleCache()
        cache.put(
            exchange="BROKER",
            symbol="EURUSD",
            timeframe="M1",
            candles=pd.DataFrame(
                dict(
                    open=[1.0, 1.0],
                    high=[1.0, 1.0],
                    low=[1.0, 1.0],
                    close=[1.0, 1.0],
                    volume=[1.0, 1.0],
                ),
                index=pd.to_datetime([-60000, 0], unit="ms", utc=True),
            ),
        )
        queue = asyncio.Queue()

        async def read(*args, **kwargs):
            return await queue.get()

        redis = Mock(xread=AsyncMock(side_effect=read), xadd=AsyncMock(), close=AsyncMock())
        manager = LiveIndicatorManager(cache, live_market_resolver())
        manager._redis = redis
        request = LiveIndicatorStreamRequest(
            market_id=1,
            account_id="123",
            symbol="EURUSD",
            timeframe="M1",
            indicator_id=1,
            parameters={"window": 2},
        )
        try:
            started = await manager.start_stream(request)
            for i, metadata in enumerate(
                (
                    {},
                    {"continuity": "v1:" + "a" * 32},
                    {"continuity": "v1:" + "b" * 32},
                    {"continuity": "bad"},
                )
            ):
                fields = dict(
                    t=str((i + 1) * 60000), o="1", h="9", l="0", c=str(3 + i * 2), v="1", **metadata
                )
                await queue.put([("candles:123:EURUSD:M1", [(str(i + 1) + "-0", fields)])])
            async with asyncio.timeout(2):
                while redis.xadd.await_count < 4:
                    await asyncio.sleep(0)
            self.assertEqual(
                [json.loads(c.args[1]["d"])["sma"] for c in redis.xadd.call_args_list],
                [2.0, 4.0, 6.0, 8.0],
            )
            for call in redis.xadd.call_args_list:
                self.assertEqual(call.args[0], started.redis_stream_key)
                self.assertEqual(set(call.args[1]), {"t", "s", "i", "d"})
        finally:
            await manager.shutdown()

    async def test_custom_market_is_rejected_before_redis_start(self):
        resolver = live_market_resolver()
        resolver.resolve.side_effect = ValueError("Custom markets do not support broker data")
        manager = LiveIndicatorManager(CandleCache(), resolver)
        manager._ensure_redis = AsyncMock()
        with self.assertRaisesRegex(ValueError, "Custom"):
            await manager.start_stream(
                LiveIndicatorStreamRequest(
                    market_id=1,
                    account_id="123",
                    symbol="EURUSD",
                    timeframe="M1",
                    indicator_id=1,
                )
            )
        manager._ensure_redis.assert_not_awaited()
        resolver.dependencies.assert_not_awaited()

    async def test_mismatched_account_is_rejected_before_market_lookup(self):
        resolver = live_market_resolver()
        manager = LiveIndicatorManager(CandleCache(), resolver)
        with self.assertRaisesRegex(ValueError, "connected broker account"):
            await manager.start_stream(
                LiveIndicatorStreamRequest(
                    market_id=1,
                    account_id="456",
                    symbol="EURUSD",
                    timeframe="M1",
                    indicator_id=1,
                )
            )
        resolver.resolve.assert_not_awaited()

    async def test_custom_basket_dependency_is_rejected_before_redis_start(self):
        resolver = live_market_resolver()
        resolver.dependencies.side_effect = ValueError(
            "Live input USDJPY requires one connected broker market"
        )
        manager = LiveIndicatorManager(CandleCache(), resolver)
        manager._ensure_redis = AsyncMock()
        with self.assertRaisesRegex(ValueError, "Live input"):
            await manager.start_stream(
                LiveIndicatorStreamRequest(
                    market_id=1,
                    account_id="123",
                    symbol="EURUSD",
                    timeframe="M1",
                    indicator_id=5,
                )
            )
        manager._ensure_redis.assert_not_awaited()
