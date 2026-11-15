"""Historical chart reads must not seed current live SMA values."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
from app.schemas_live import LiveIndicatorStreamRequest
from app.services.candle_cache import CandleCache
from app.services.historical_indicator_service import run_historical_indicator
from app.services.live_indicator_manager import LiveIndicatorManager


def candles(times, close):
    return pd.DataFrame(
        {field: [close] * len(times) for field in ("open", "high", "low", "close", "volume")},
        index=pd.to_datetime(times, unit="ms", utc=True),
    )


class LiveHistoryNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_historical_chart_read_cannot_contaminate_first_live_sma(self):
        for window in (2, 5, 20):
            with self.subTest(symbol="BTCUSD", timeframe="M1", window=window):
                await self._assert_first_live_sma(window)

    async def _assert_first_live_sma(self, window):
        cache = CandleCache()
        with patch(
            "app.services.historical_indicator_service.get_candles",
            new=AsyncMock(return_value=candles([i * 60000 for i in range(window)], 10.0)),
        ):
            await run_historical_indicator(
                indicator_id=1,
                symbol="BTCUSD",
                exchange=None,
                timeframe="M1",
                start_ms=0,
                end_ms=window * 60000,
                limit=None,
                custom_parameters={"window": window},
                candle_cache=cache,
            )
        queue = asyncio.Queue()

        async def read(*args, **kwargs):
            return await queue.get()

        redis = Mock(xread=AsyncMock(side_effect=read), xadd=AsyncMock(), close=AsyncMock())
        manager = LiveIndicatorManager(cache)
        manager._redis = redis
        try:
            with patch(
                "app.services.live_indicator_manager.get_candles",
                new=AsyncMock(
                    return_value=candles([86_400_000 + i * 60000 for i in range(window)], 100.0)
                ),
            ):
                await manager.start_stream(
                    LiveIndicatorStreamRequest(
                        account_id="123",
                        symbol="BTCUSD",
                        timeframe="M1",
                        indicator_id=1,
                        parameters={"window": window},
                    )
                )
            await queue.put(
                [
                    (
                        "candles:123:BTCUSD:M1",
                        [
                            (
                                "1-0",
                                {
                                    "t": str(86_400_000 + window * 60000),
                                    "o": "100",
                                    "h": "100",
                                    "l": "100",
                                    "c": "100",
                                    "v": "1",
                                },
                            )
                        ],
                    )
                ]
            )
            async with asyncio.timeout(2):
                while redis.xadd.await_count < 1:
                    await asyncio.sleep(0)
            self.assertEqual(json.loads(redis.xadd.call_args.args[1]["d"])["sma"], 100.0)
        finally:
            await manager.shutdown()

    async def test_bounded_history_preserves_cached_latest_candles(self):
        cache = CandleCache()
        for end, frame in (
            (None, candles([600000, 660000], 100.0)),
            (120000, candles([0, 60000], 10.0)),
        ):
            with patch(
                "app.services.historical_indicator_service.get_candles",
                new=AsyncMock(return_value=frame),
            ):
                await run_historical_indicator(
                    indicator_id=1,
                    symbol="TEST",
                    exchange=None,
                    timeframe="M1",
                    start_ms=None,
                    end_ms=end,
                    limit=2,
                    custom_parameters={"window": 2},
                    candle_cache=cache,
                )
        tail = cache.get_tail(exchange=None, symbol="TEST", timeframe="M1", bars=2)
        assert tail is not None
        self.assertEqual(tail["close"].tolist(), [100.0, 100.0])
