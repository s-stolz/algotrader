from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock

from app.stream_consumer import StreamConsumer

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_module.Redis = object
redis_module.asyncio = redis_asyncio_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)


def _msg(
    message_id: bytes, timestamp: int, close: float, high: float, low: float
) -> tuple[bytes, dict[bytes, bytes]]:
    return (
        message_id,
        {
            b"t": str(timestamp).encode(),
            b"o": b"1.0",
            b"h": str(high).encode(),
            b"l": str(low).encode(),
            b"c": str(close).encode(),
            b"v": b"1",
        },
    )


class StreamConsumerTests(unittest.TestCase):
    def test_process_messages_emits_only_closed_candles(self) -> None:
        consumer = StreamConsumer(redis=AsyncMock(), account_id="1")
        stream_key = "candles:1:EURUSD:M1"

        messages = [
            (
                b"candles:1:EURUSD:M1",
                [
                    _msg(b"1-0", 1000, 1.10, 1.20, 1.00),
                    _msg(b"2-0", 1000, 1.12, 1.25, 0.99),
                    _msg(b"3-0", 1060, 1.13, 1.22, 1.01),
                ],
            )
        ]

        closed, last_id = consumer._process_stream_messages(stream_key, messages)
        self.assertEqual(last_id, "3-0")
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["t"], 1000)
        self.assertEqual(closed[0]["h"], 1.25)
        self.assertEqual(closed[0]["l"], 0.99)
        self.assertEqual(closed[0]["c"], 1.12)

        next_messages = [(b"candles:1:EURUSD:M1", [_msg(b"4-0", 1120, 1.20, 1.30, 1.05)])]
        next_closed, next_last_id = consumer._process_stream_messages(stream_key, next_messages)
        self.assertEqual(next_last_id, "4-0")
        self.assertEqual(len(next_closed), 1)
        self.assertEqual(next_closed[0]["t"], 1060)


if __name__ == "__main__":
    unittest.main()
