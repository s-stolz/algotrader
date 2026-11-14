import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.candle_stream import BATCH_SIZE, candle_batches


class CandleStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_batches_yield_control_and_close_cursor_on_cancel(self):
        calls = []

        class Result:
            async def partitions(self, size):
                self.size = size
                for i in range(10):
                    calls.append(i)
                    yield [SimpleNamespace(_mapping={"timestamp_ms": i, "close": 1.0})]

            close = AsyncMock()

        result = Result()
        session = SimpleNamespace(stream=AsyncMock(return_value=result))
        stream = candle_batches(session, 1, 1, 0, 100)
        self.assertEqual((await anext(stream))[0]["timestamp_ms"], 0)
        self.assertEqual(result.size, BATCH_SIZE)
        heartbeat = []
        asyncio.get_running_loop().call_soon(lambda: heartbeat.append(True))
        await anext(stream)
        self.assertEqual(heartbeat, [True])
        await stream.aclose()
        result.close.assert_awaited_once()
        self.assertEqual(calls, [0, 1])


class CandleStreamPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import os

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        url = os.getenv("CANDLE_STREAM_TEST_DATABASE_URL")
        if not url:
            self.skipTest("CANDLE_STREAM_TEST_DATABASE_URL requires a disposable database")
        if not url.endswith("/equity_stream_test"):
            raise ValueError("Use the disposable equity_stream_test database")
        self.engine = create_async_engine(url)
        self.session = async_sessionmaker(self.engine)()
        await self.session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        await self.session.execute(text("""CREATE TEMP TABLE candles (
            symbol_id integer, timestamp_utc timestamptz, open double precision,
            high double precision, low double precision, close double precision,
            volume double precision)"""))
        await self.session.execute(text("""INSERT INTO candles SELECT 1,
            to_timestamp(i * 60), 1, 2, .5, 1.5 + i * .0001, 10
            FROM generate_series(0, 4096) i"""))
        await self.session.commit()

    async def asyncTearDown(self):
        if hasattr(self, "session"):
            await self.session.close()
            await self.engine.dispose()

    async def test_stream_matches_bulk_m1_and_bucketing(self):
        from app.crud import get_candles

        for timeframe in [1, 7]:
            with self.subTest(timeframe=timeframe):
                expected = await get_candles(self.session, 1, timeframe, 60_000, 4090 * 60_000)
                batches = [
                    batch
                    async for batch in candle_batches(
                        self.session, 1, timeframe, 60_000, 4090 * 60_000
                    )
                ]
                self.assertTrue(all(len(batch) <= BATCH_SIZE for batch in batches))
                self.assertEqual([row for batch in batches for row in batch], expected)

    async def test_empty_aggregate_falls_back_and_cursor_can_close_early(self):
        from app.crud import CAGG_VIEW_BY_MINUTES, get_candles
        from sqlalchemy import text

        timeframe = next(iter(CAGG_VIEW_BY_MINUTES))
        view = CAGG_VIEW_BY_MINUTES[timeframe]
        await self.session.execute(
            text(
                f"CREATE TEMP TABLE {view} AS SELECT timestamp_utc AS bucket_ts, "
                "symbol_id, open, high, low, close, volume FROM candles WHERE false"
            )
        )
        expected = await get_candles(self.session, 1, timeframe, 0, 4096 * 60_000)
        actual = [
            row
            async for batch in candle_batches(self.session, 1, timeframe, 0, 4096 * 60_000)
            for row in batch
        ]
        self.assertEqual(actual, expected)
        stream = candle_batches(self.session, 1, 1, 0, 4096 * 60_000)
        await anext(stream)
        await stream.aclose()
        self.assertEqual((await self.session.execute(text("SELECT 1"))).scalar(), 1)


class CandleStreamHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_response_keeps_health_responsive_and_closes_on_disconnect(self):
        import os
        import socket
        from unittest.mock import patch

        if os.getenv("RUN_CANDLE_STREAM_HTTP_TESTS") != "1":
            self.skipTest("Set RUN_CANDLE_STREAM_HTTP_TESTS=1 for loopback HTTP checks")
        os.environ.setdefault("TIMESCALEDB_USER", "test")
        os.environ.setdefault("TIMESCALEDB_PASSWORD", "test")
        os.environ.setdefault("TIMESCALEDB_HOST", "localhost")
        os.environ.setdefault("TIMESCALEDB_PORT", "5432")
        os.environ.setdefault("TIMESCALEDB_DB", "test")
        import app.database
        import httpx
        import main
        import uvicorn

        stats = {"fetched": 0, "closed": 0}

        class Cursor:
            async def partitions(self, size):
                for start in range(0, 362117, size):
                    stats["fetched"] += 1
                    yield [
                        SimpleNamespace(
                            _mapping=dict(
                                timestamp_ms=i * 60000,
                                open=1.0,
                                high=2.0,
                                low=0.5,
                                close=1.5,
                                volume=10.0,
                            )
                        )
                        for i in range(start, min(start + size, 362117))
                    ]

            async def close(self):
                stats["closed"] += 1

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def stream(self, *args):
                return Cursor()

        async def db():
            yield Session()

        original = dict(main.app.dependency_overrides)
        main.app.dependency_overrides[main.get_db] = db
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", lifespan="off"))
        with (
            patch.object(app.database, "AsyncSessionLocal", Session),
            patch.object(main.market_cache, "ensure_market_cache", AsyncMock()),
            patch.object(main.market_cache, "resolve_symbol_id", return_value=1),
        ):
            task = asyncio.create_task(server.serve(sockets=[sock]))
            try:
                while not server.started:
                    await asyncio.sleep(0.01)
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                    await self.assert_http_stream(client, stats)
            finally:
                server.should_exit = True
                await task
                main.app.dependency_overrides = original

    async def assert_http_stream(self, client, stats):
        import json
        import time

        params = dict(timeframe="M1", start_ms=0, end_ms=362117 * 60000)
        count = 0
        request_started = time.monotonic()
        async with client.stream(
            "GET",
            "/candles/EURUSD/stream",
            params=params,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                frame = json.loads(line)
                if frame["type"] == "candles":
                    if count == 0:
                        self.assertLess(time.monotonic() - request_started, 1.0)
                    self.assertLessEqual(len(frame["candles"]), BATCH_SIZE)
                    count += len(frame["candles"])
                    if count % (BATCH_SIZE * 10) == 0:
                        start = time.monotonic()
                        self.assertEqual((await client.get("/health")).status_code, 200)
                        self.assertLess(time.monotonic() - start, 1.0)
        self.assertEqual(count, 362117)
        closed = stats["closed"]
        stats["fetched"] = 0
        async with client.stream(
            "GET",
            "/candles/EURUSD/stream",
            params=params,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            async for _ in response.aiter_lines():
                break
        await asyncio.sleep(0.2)
        fetched = stats["fetched"]
        await asyncio.sleep(0.1)
        self.assertGreater(stats["closed"], closed)
        self.assertLess(fetched, 354)
        self.assertEqual(stats["fetched"], fetched)
