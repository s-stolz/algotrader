from __future__ import annotations

import asyncio
import json
import logging
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from app.db_client import DatabaseClient
from app.stream_consumer import StreamConsumer
from main import IngestionService, SymbolRuntimeState
from redis.asyncio import Redis

STREAM = "candles:1:EURUSD:M1"


def _msg(message_id: bytes, timestamp: int, close: float = 1.1):
    return (
        message_id,
        {
            b"t": str(timestamp).encode(),
            b"o": b"1.0",
            b"h": b"1.3",
            b"l": b"0.9",
            b"c": str(close).encode(),
            b"v": b"1",
        },
    )


class ControlledRedis(Redis):
    def __init__(self, consumer, batches):
        self.consumer = consumer
        self.batches = iter(batches)
        self.cursors = []

    async def xread(self, streams, **kwargs):
        self.cursors.append(streams[STREAM])
        batch = next(self.batches, None)
        if isinstance(batch, Exception):
            raise batch
        if batch is None:
            self.consumer.stop()
            return []
        return [(STREAM.encode(), batch)]


class StreamConsumerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stored = {}
        self.write_calls = 0
        self.fail_write = None
        self.ambiguous = False
        self.consumer = StreamConsumer(redis=AsyncMock(), account_id="1")
        self.db_client = DatabaseClient()
        self.db_client._client.client.close()
        self.db_client._client.client = httpx.Client(transport=httpx.MockTransport(self.persist))
        self.addCleanup(self.db_client.close)
        self.service = IngestionService.__new__(IngestionService)
        self.service.db_client = self.db_client
        self.service.logger = logging.getLogger("test.ingestion")
        chunk_size = patch.object(self.service, "CHUNK_SIZE", 2)
        chunk_size.start()
        self.addCleanup(chunk_size.stop)
        self.service._shutdown = False
        self.service._state_by_id = {1: SymbolRuntimeState(1, "EURUSD", "FX", STREAM)}
        self.service._state_by_id[1].live_ready.set()

    def persist(self, request):
        self.write_calls += 1
        should_fail = self.write_calls == self.fail_write
        if not should_fail or self.ambiguous:
            for candle in json.loads(request.content)["candles"]:
                # Match the accessor's (Market, timestamp) ON CONFLICT DO NOTHING contract.
                self.stored.setdefault(candle["timestamp_ms"], candle)
        return httpx.Response(500 if should_fail else 200, json={"added_candles": 0})

    async def consume(self, batches):
        redis = ControlledRedis(self.consumer, batches)
        self.consumer.redis = redis

        async def retry_without_delay(_seconds):
            pass

        with patch("app.stream_consumer.asyncio.sleep", retry_without_delay):
            await asyncio.wait_for(
                self.consumer.consume_stream(STREAM, 1, self.service.write_candles_callback), 2
            )
        return redis

    async def test_same_minute_repeats_and_out_of_order_store_only_closed_candles(self):
        await self.consume(
            [
                [_msg(b"1-0", 60000), _msg(b"2-0", 60000, 1.2), _msg(b"3-0", 120000)],
                [_msg(b"2-0", 60000, 9), _msg(b"3-0", 120000), _msg(b"4-0", 180000)],
            ]
        )
        self.assertEqual(sorted(self.stored), [60000, 120000])
        self.assertEqual(self.stored[60000]["close"], 1.2)

    async def test_partial_batch_failure_retries_all_closed_candles_before_reading_more(self):
        for ambiguous in (False, True):
            with self.subTest(ambiguous=ambiguous):
                self.stored.clear()
                self.write_calls = 0
                self.fail_write = 2
                self.ambiguous = ambiguous
                self.consumer = StreamConsumer(redis=AsyncMock(), account_id="1")
                redis = await self.consume(
                    [
                        [_msg(b"1-0", 60000)],
                        [
                            _msg(b"2-0", 60000, 1.2),
                            _msg(b"3-0", 120000),
                            _msg(b"4-0", 180000),
                            _msg(b"5-0", 240000),
                        ],
                        [_msg(b"6-0", 300000)],
                    ]
                )
                self.assertEqual(sorted(self.stored), [60000, 120000, 180000, 240000])
                self.assertEqual(self.stored[60000]["close"], 1.2)
                self.assertEqual(redis.cursors, ["0-0", "1-0", "5-0", "6-0"])

    async def test_redis_read_failure_retains_previous_open_candle(self):
        await self.consume(
            [[_msg(b"1-0", 60000)], OSError("Redis unavailable"), [_msg(b"2-0", 120000)]]
        )
        self.assertEqual(sorted(self.stored), [60000])

    async def test_cancellation_during_retry_leaves_batch_replayable(self):
        self.fail_write = 1
        redis = ControlledRedis(self.consumer, [[_msg(b"1-0", 60000)], [_msg(b"2-0", 120000)]])
        self.consumer.redis = redis
        retrying = asyncio.Event()

        async def wait_in_retry(_seconds):
            retrying.set()
            await asyncio.Event().wait()

        with patch("app.stream_consumer.asyncio.sleep", wait_in_retry):
            task = asyncio.create_task(
                self.consumer.consume_stream(STREAM, 1, self.service.write_candles_callback)
            )
            try:
                await asyncio.wait_for(retrying.wait(), 2)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        self.assertEqual(self.stored, {})
        redis = await self.consume([[_msg(b"2-0", 120000)], [_msg(b"3-0", 180000)]])
        self.assertEqual(sorted(self.stored), [60000, 120000])
        self.assertEqual(redis.cursors[0], "1-0")


if __name__ == "__main__":
    unittest.main()
