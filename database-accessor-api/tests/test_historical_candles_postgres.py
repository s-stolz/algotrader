"""Opt-in real API/Timescale tests; use only a disposable vibe9_* database."""

import asyncio
import os
import unittest
from uuid import uuid4

import httpx
from app import market_cache
from app.models import metadata
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("HISTORY_TEST_DATABASE_URL")


def bar(timestamp, value=2):
    return dict(
        timestamp_ms=timestamp,
        open=value,
        high=value + 2,
        low=value - 1,
        close=value + 1,
        volume=value * 10,
    )


@unittest.skipUnless(DATABASE_URL, "Set HISTORY_TEST_DATABASE_URL for live Timescale tests")
class HistoricalStorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        assert DATABASE_URL is not None
        if not (make_url(DATABASE_URL).database or "").startswith("vibe9_"):
            raise RuntimeError("Historical integration tests require a disposable vibe9_* DB")
        self.schema = "vibe9_" + uuid4().hex
        self.admin = create_async_engine(DATABASE_URL)
        async with self.admin.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            await connection.execute(text(f"CREATE SCHEMA {self.schema}"))
        self.engine = create_async_engine(
            DATABASE_URL, connect_args={"server_settings": {"search_path": f"{self.schema},public"}}
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: metadata.create_all(sync, checkfirst=False))
            await connection.execute(
                text(
                    "SELECT create_hypertable('candles', 'timestamp_utc', "
                    "chunk_time_interval => INTERVAL '1 day')"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE candles SET (timescaledb.compress=true, "
                    "timescaledb.compress_segmentby='symbol_id', "
                    "timescaledb.compress_orderby='timestamp_utc DESC')"
                )
            )
        # Import the API only after supplying a syntactically valid unused default DB URL.
        for key, value in {"TIMESCALEDB_PORT": "5432", "TIMESCALEDB_HOST": "unused"}.items():
            os.environ.setdefault(key, value)
        from app.database import get_db
        from main import app

        self.app = app
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

        async def session():
            async with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = session
        market_cache._rebuild_cache([])
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        response = await self.client.post(
            "/markets",
            json={"symbol": "EURUSD", "exchange": "FX", "market_type": "forex", "min_move": 0.01},
        )
        response.raise_for_status()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.app.dependency_overrides.clear()
        market_cache._rebuild_cache([])
        await self.engine.dispose()
        async with self.admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))
        await self.admin.dispose()

    async def write(self, bars, *, historical=False, start=60000, end=299999):
        payload = {"symbol": "EURUSD", "exchange": "FX", "candles": bars}
        if historical:
            payload.update(start_ms=start, end_ms=end)
        response = await self.client.post(
            "/candles/historical" if historical else "/candles", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def read(self, timeframe="M1"):
        response = await self.client.get("/candles/EURUSD", params={"timeframe": timeframe})
        response.raise_for_status()
        return response.json()

    async def test_correction_replay_stale_live_and_omissions(self):
        await self.write([bar(t, 1) for t in (0, 60000, 120000, 180000, 300000)])
        corrected = [bar(60000, 8), bar(180000, 9)]
        await self.write(corrected, historical=True)
        # Discard the receipt and replay as after an uncertain HTTP outcome.
        await self.write(corrected, historical=True)
        await self.write([bar(60000, 1), bar(180000, 1)])
        actual = await self.read()
        self.assertEqual(
            actual, [bar(0, 1), bar(60000, 8), bar(120000, 1), bar(180000, 9), bar(300000, 1)]
        )

    async def test_concurrent_live_and_history_on_existing_and_absent_rows(self):
        for minute in range(1, 13):
            timestamp = minute * 60000
            if minute % 2:
                await self.write([bar(timestamp, 1)])
            await asyncio.gather(
                self.write([bar(timestamp, 8)], historical=True, end=1000000),
                self.write([bar(timestamp, 1)]),
            )
        self.assertEqual(await self.read(), [bar(i * 60000, 8) for i in range(1, 13)])

    async def test_compressed_correction_and_higher_timeframe_refresh(self):
        await self.write([bar(60000, 1), bar(120000, 1)])
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE MATERIALIZED VIEW candles_agg_h1 WITH (timescaledb.continuous) AS "
                    "SELECT time_bucket(INTERVAL '1 hour', timestamp_utc) bucket_ts, symbol_id, "
                    "first(open,timestamp_utc) open, max(high) high, min(low) low, "
                    "last(close,timestamp_utc) close, sum(volume) volume "
                    "FROM candles GROUP BY bucket_ts,symbol_id WITH NO DATA"
                )
            )
        async with self.engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(
                text("CALL refresh_continuous_aggregate('candles_agg_h1', NULL, NULL)")
            )
            await connection.execute(text("SELECT compress_chunk(show_chunks('candles'))"))
            count = await connection.scalar(
                text(
                    "SELECT count(*) FROM timescaledb_information.chunks "
                    "WHERE hypertable_schema=:schema "
                    "AND hypertable_name='candles' AND is_compressed"
                ),
                {"schema": self.schema},
            )
            self.assertGreater(count, 0)
        await self.write([bar(60000, 8), bar(180000, 9)], historical=True)
        await self.write([bar(60000, 8), bar(180000, 9)], historical=True)
        await self.write([bar(60000, 1), bar(180000, 1)])
        self.assertEqual(await self.read(), [bar(60000, 8), bar(120000, 1), bar(180000, 9)])
        async with self.engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(
                text("CALL refresh_continuous_aggregate('candles_agg_h1', NULL, NULL)")
            )
        aggregated = await self.read("H1")
        self.assertEqual(
            aggregated, [dict(timestamp_ms=0, open=8, high=11, low=0, close=10, volume=180)]
        )

    async def test_invalid_interval_open_minute_and_outside_values_write_nothing(self):
        from datetime import datetime, timezone

        open_minute = int(datetime.now(timezone.utc).timestamp() // 60) * 60000
        for start, end, bars in [
            (60000, 119999, [bar(0)]),
            (120000, 60000, [bar(60000)]),
            (open_minute, open_minute + 59999, [bar(open_minute)]),
            (60000, 119999, [bar(60001)]),
        ]:
            response = await self.client.post(
                "/candles/historical",
                json={"symbol": "EURUSD", "start_ms": start, "end_ms": end, "candles": bars},
            )
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(await self.read(), [])
