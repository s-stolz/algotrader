import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from app.redis_consumer import RedisConsumer


class CandleCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_does_not_escape_candle_fanout_and_legacy_stays_compatible(self):
        consumer = RedisConsumer("unused", 1, "123")
        queue = asyncio.Queue()
        consumer.redis = Mock(
            xread=AsyncMock(side_effect=lambda *a, **k: queue.get()), close=AsyncMock()
        )

        # Use an async adapter because XREAD itself waits for data.
        async def read(*args, **kwargs):
            return await queue.get()

        consumer.redis.xread.side_effect = read
        consumer.is_connected = True
        consumer.subscription_manager = Mock()
        try:
            await consumer.start_candle_stream("EURUSD", "M1")
            for metadata in ({}, {"continuity": "v1:" + "a" * 32}, {"continuity": "invalid"}):
                fields = dict(t="60000", o="1", h="3", l="0", c="2", v="4", **metadata)
                await queue.put([("candles:123:EURUSD:M1", [("1-0", fields)])])
            async with asyncio.timeout(1):
                while consumer.subscription_manager.broadcast_candle.call_count < 3:
                    await asyncio.sleep(0)
            expected = dict(timestamp_ms=60000, open=1.0, high=3.0, low=0.0, close=2.0, volume=4.0)
            for call in consumer.subscription_manager.broadcast_candle.call_args_list:
                self.assertEqual(call.args, ("EURUSD", "M1", expected))
        finally:
            await consumer.disconnect()
