"""Rolling-range values survive historical formatting and live publication."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
from app import get_indicator_metadata
from app.schemas_live import LiveIndicatorStreamRequest
from app.services.candle_cache import CandleCache
from app.services.historical_indicator_service import run_historical_indicator
from app.services.live_indicator_manager import LiveIndicatorManager

from tests.live_market_fixtures import live_market_resolver


class RollingRangeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_historical_and_live_outputs(self):
        candles = pd.DataFrame(
            dict(
                open=[5.0, 5.0],
                high=[9.0, 7.0],
                low=[1.0, 3.0],
                close=[5.0, 5.0],
                volume=[1.0, 1.0],
            ),
            index=pd.to_datetime([-60000, 0], unit="ms", utc=True),
        )
        metadata = get_indicator_metadata(8)
        self.assertTrue(metadata["supports_live"])
        self.assertEqual(set(metadata["outputs"]), {"highest_high", "lowest_low"})
        with patch(
            "app.services.historical_indicator_service.get_candles",
            new=AsyncMock(return_value=candles),
        ):
            response = await run_historical_indicator(
                indicator_id=8,
                symbol="TEST",
                exchange=None,
                timeframe="M1",
                start_ms=0,
                end_ms=60000,
                limit=None,
                custom_parameters={"window": 2},
                candle_cache=CandleCache(),
            )
        json.dumps(response, allow_nan=False)
        rows = response["data"]["indicator_data"]
        self.assertEqual(rows[-1]["highest_high"], 9)
        self.assertEqual(rows[-1]["lowest_low"], 1)
        cache = CandleCache()
        cache.put(exchange="BROKER", symbol="TEST", timeframe="M1", candles=candles)
        queue = asyncio.Queue()

        async def read(*args, **kwargs):
            return await queue.get()

        redis = Mock(xread=AsyncMock(side_effect=read), xadd=AsyncMock(), close=AsyncMock())
        manager = LiveIndicatorManager(cache, live_market_resolver("TEST"))
        manager._redis = redis
        try:
            await manager.start_stream(
                LiveIndicatorStreamRequest(
                    market_id=1,
                    account_id="123",
                    symbol="TEST",
                    timeframe="M1",
                    indicator_id=8,
                    parameters={"window": 2},
                )
            )
            for i, (timestamp, high, low) in enumerate(
                [(60000, 8, 2), (60000, 10, 0), (120000, 6, 4)]
            ):
                await queue.put(
                    [
                        (
                            "candles:123:TEST:M1",
                            [
                                (
                                    f"{i + 1}-0",
                                    dict(
                                        t=str(timestamp),
                                        o="5",
                                        h=str(high),
                                        l=str(low),
                                        c="5",
                                        v="1",
                                    ),
                                )
                            ],
                        )
                    ]
                )
            async with asyncio.timeout(2):
                while redis.xadd.await_count < 3:
                    await asyncio.sleep(0)
            self.assertEqual(
                [json.loads(call.args[1]["d"]) for call in redis.xadd.call_args_list],
                [
                    dict(highest_high=8, lowest_low=2),
                    dict(highest_high=10, lowest_low=0),
                    dict(highest_high=10, lowest_low=0),
                ],
            )
        finally:
            await manager.shutdown()
