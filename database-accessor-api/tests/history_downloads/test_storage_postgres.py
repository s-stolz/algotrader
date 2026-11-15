"""Run only against an explicitly supplied disposable Timescale database."""

import asyncio
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from app import crud, market_cache
from app.database import get_db
from app.models import candles
from main import app
from sqlalchemy import insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("HISTORY_DOWNLOAD_TEST_DATABASE_URL")
MIGRATIONS = Path(__file__).resolve().parents[3] / "timescaledb-init/migrations"
SPEC = dict(
    symbol="EURUSD",
    exchange="TEST BROKER",
    market_type="Forex",
    min_move=0.00001,
    timezone="UTC",
    settlement_currency="USD",
    contract_multiplier=1,
    minimum_quantity=1,
    quantity_step=1,
    source_type="broker",
    broker_provider="ctrader",
    broker_account_id="test-account",
    broker_environment="demo",
    broker_symbol_id=17,
)


def bar(timestamp, value=2):
    return dict(
        timestamp_ms=timestamp, open=value, high=value + 1, low=value - 1, close=value, volume=10
    )


@unittest.skipUnless(
    DATABASE_URL, "Set HISTORY_DOWNLOAD_TEST_DATABASE_URL for live Timescale tests"
)
class DownloadPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        assert DATABASE_URL is not None
        if not (make_url(DATABASE_URL).database or "").startswith("vibe9_"):
            raise RuntimeError("Download acceptance requires a disposable vibe9_* database")
        self.schema = "download_" + uuid4().hex
        self.admin = create_async_engine(DATABASE_URL)
        async with self.admin.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            await connection.execute(text(f"CREATE SCHEMA {self.schema}"))
        self.engine = create_async_engine(
            DATABASE_URL,
            connect_args={
                "server_settings": {"search_path": f"{self.schema},public"},
            },
        )
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                CREATE TABLE markets (
                    symbol_id SERIAL PRIMARY KEY, symbol VARCHAR(10) NOT NULL,
                    exchange VARCHAR(20) NOT NULL, market_type VARCHAR(20) NOT NULL,
                    min_move DOUBLE PRECISION NOT NULL, timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
                    settlement_currency VARCHAR(12) NOT NULL,
                    contract_multiplier DOUBLE PRECISION NOT NULL,
                    minimum_quantity DOUBLE PRECISION NOT NULL,
                    quantity_step DOUBLE PRECISION NOT NULL,
                    UNIQUE(symbol, exchange)
                )
            """))
            await connection.execute(text("""
                INSERT INTO markets(symbol, exchange, market_type, min_move, settlement_currency,
                                    contract_multiplier, minimum_quantity, quantity_step)
                VALUES ('LEGACY', 'CSV', 'Forex', 0.01, 'USD', 1, 1, 1)
            """))
            raw = await connection.get_raw_connection()
            assert raw.driver_connection is not None
            await raw.driver_connection.execute(
                (MIGRATIONS / "V023__market_sources.sql").read_text()
            )
            await connection.run_sync(lambda sync: candles.create(sync))
            await connection.execute(text("SELECT create_hypertable('candles', 'timestamp_utc')"))
            await raw.driver_connection.execute(
                (MIGRATIONS / "V024__history_download_jobs.sql").read_text()
            )
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

        async def database():
            async with self.factory() as session:
                yield session

        app.dependency_overrides[get_db] = database
        market_cache._rebuild_cache([])
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        with patch("main.verify_broker_market", new=AsyncMock()):
            created = await self.client.post("/markets", json=SPEC)
        created.raise_for_status()
        self.market_id = created.json()["symbol_id"]
        async with self.engine.begin() as connection:
            await connection.execute(
                insert(candles).values(
                    symbol_id=self.market_id,
                    timestamp_utc=datetime.fromtimestamp(600, timezone.utc),
                    open=1,
                    high=3,
                    low=1,
                    close=2,
                    volume=5,
                )
            )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        market_cache._rebuild_cache([])
        await self.engine.dispose()
        async with self.admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))
        await self.admin.dispose()

    async def accept(self, request_id=None):
        return await self.client.post(
            "/history-download-jobs",
            json=dict(
                request_id=request_id or str(uuid4()),
                market_id=self.market_id,
                start_ms=0,
            ),
        )

    async def claim(self, job_id, owner="owner1"):
        response = await self.client.post(
            f"/history-download-jobs/{job_id}/claim",
            json=dict(
                owner_token=owner,
                lease_seconds=120,
            ),
        )
        response.raise_for_status()
        return response.json()

    async def page(self, job, next_ms=300000, values=None):
        values = values if values is not None else [bar(300000), bar(360000)]
        response = await self.client.post(
            f"/history-download-jobs/{job['id']}/pages",
            json=dict(
                owner_token=job["owner_token"],
                revision=job["revision"],
                expected_cursor_ms=job["cursor_ms"],
                next_cursor_ms=next_ms,
                fetched_count=len(values),
                candles=values,
            ),
        )
        response.raise_for_status()
        return response.json()

    async def test_migration_preserves_legacy_identity_and_database_source_constraints(self):
        legacy = (await self.client.get("/markets/id/1")).json()
        self.assertEqual((legacy["symbol"], legacy["source_type"]), ("LEGACY", "custom"))
        async with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                await connection.execute(
                    text("UPDATE markets SET source_type='broker' WHERE symbol_id=1")
                )
        async with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                await connection.execute(
                    text("UPDATE markets SET broker_symbol_id=99 WHERE symbol_id=:id"),
                    {"id": self.market_id},
                )

    async def test_accept_and_claim_races_keep_one_owner_and_one_active_request(self):
        request_id = str(uuid4())
        receipts = await asyncio.gather(self.accept(request_id), self.accept(request_id))
        self.assertEqual([response.status_code for response in receipts], [200, 200])
        competing = await self.accept()
        self.assertEqual(competing.status_code, 409)
        claims = await asyncio.gather(self.claim(request_id, "one"), self.claim(request_id, "two"))
        claimed = [job for job in claims if job is not None]
        self.assertEqual(len(claimed), 1)
        pages = await asyncio.gather(self.page(claimed[0]), self.page(claimed[0]))
        self.assertEqual(len([job for job in pages if job is not None]), 1)
        current = (await self.client.get(f"/history-download-jobs/{request_id}")).json()
        self.assertEqual((current["inserted_count"], current["fetched_count"]), (2, 2))

    async def test_restart_reclaims_expired_lease_and_cancellation_fences_old_pages(self):
        job = await self.claim((await self.accept()).json()["id"])
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE history_download_jobs "
                    "SET lease_expires_at=now()-interval '1 second' WHERE id=:id"
                ),
                {"id": job["id"]},
            )
        await self.engine.dispose()
        replacement = await self.claim(job["id"], "replacement")
        self.assertIsNone(await self.page(job))
        confirmed = await self.page(replacement)
        cancelled = await self.client.post(f"/history-download-jobs/{job['id']}/cancel")
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertIsNone(await self.page(confirmed, 0, []))
        retry = await self.client.post(f"/history-download-jobs/{job['id']}/retry")
        self.assertEqual((retry.json()["cursor_ms"], retry.json()["inserted_count"]), (300000, 2))
        deleted = await self.client.delete("/markets/EURUSD", params={"exchange": "TEST BROKER"})
        self.assertEqual(deleted.status_code, 409)

    async def test_cancel_page_race_is_serialized_and_database_blocks_active_deletion(self):
        job = await self.claim((await self.accept()).json()["id"])
        async with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                await connection.execute(
                    text("DELETE FROM markets WHERE symbol_id=:id"), {"id": self.market_id}
                )
        page, cancelled = await asyncio.gather(
            self.page(job),
            self.client.post(f"/history-download-jobs/{job['id']}/cancel"),
        )
        self.assertEqual(cancelled.json()["status"], "cancelled")
        current = (await self.client.get(f"/history-download-jobs/{job['id']}")).json()
        self.assertEqual(current["inserted_count"], 0 if page is None else 2)
        self.assertIsNone(await self.page(job))

    async def test_extension_preserves_existing_candles_and_refreshes_old_aggregates(self):
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                CREATE MATERIALIZED VIEW candles_agg_m5 WITH (timescaledb.continuous) AS
                SELECT symbol_id, time_bucket(INTERVAL '5 minutes', timestamp_utc) AS bucket,
                       first(open, timestamp_utc) AS open, max(high) AS high, min(low) AS low,
                       last(close, timestamp_utc) AS close, sum(volume) AS volume
                FROM candles GROUP BY symbol_id, bucket WITH NO DATA
            """))
        job = await self.claim((await self.accept()).json()["id"])
        async with self.engine.begin() as connection:
            await connection.execute(
                insert(candles).values(
                    symbol_id=self.market_id,
                    timestamp_utc=datetime.fromtimestamp(300, timezone.utc),
                    open=20,
                    high=30,
                    low=10,
                    close=20,
                    volume=50,
                )
            )
        job = await self.page(job)
        self.assertEqual(job["inserted_count"], 1)
        job = await self.page(job, 0, [])
        response = await self.client.post(
            f"/history-download-jobs/{job['id']}/transition",
            json=dict(
                owner_token=job["owner_token"],
                revision=job["revision"],
                status="completed",
            ),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "completed")
        async with self.engine.connect() as connection:
            raw = await connection.scalar(
                text(
                    "SELECT close FROM candles "
                    "WHERE symbol_id=:id AND timestamp_utc=to_timestamp(300)"
                ),
                {"id": self.market_id},
            )
            self.assertEqual(raw, 20)
            result = await connection.execute(
                text(
                    "SELECT volume FROM candles_agg_m5 "
                    "WHERE symbol_id=:id AND bucket=to_timestamp(300)"
                ),
                {"id": self.market_id},
            )
            self.assertEqual(result.scalar_one(), 60)

    async def test_real_refresh_failure_keeps_confirmed_pages_and_allows_completion_retry(self):
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                CREATE FUNCTION fail_download_refresh(value DOUBLE PRECISION)
                RETURNS DOUBLE PRECISION LANGUAGE plpgsql IMMUTABLE AS $$
                BEGIN
                    RAISE EXCEPTION 'forced aggregate refresh failure';
                END;
                $$
            """))
            await connection.execute(text("""
                CREATE MATERIALIZED VIEW candles_agg_m5 WITH (timescaledb.continuous) AS
                SELECT symbol_id, time_bucket(INTERVAL '5 minutes', timestamp_utc) AS bucket,
                       first(fail_download_refresh(open), timestamp_utc) AS open,
                       max(high) AS high, min(low) AS low,
                       last(close, timestamp_utc) AS close, sum(volume) AS volume
                FROM candles GROUP BY symbol_id, bucket WITH NO DATA
            """))
        job = await self.claim((await self.accept()).json()["id"])
        job = await self.page(job)
        job = await self.page(job, 0, [])
        payload = dict(owner_token=job["owner_token"], revision=job["revision"], status="completed")
        async with self.engine.connect() as connection:
            rows_before = (
                (
                    await connection.execute(
                        select(candles)
                        .where(candles.c.symbol_id == self.market_id)
                        .order_by(candles.c.timestamp_utc)
                    )
                )
                .mappings()
                .all()
            )
        with self.assertRaises(DBAPIError) as failed_refresh:
            await self.client.post(f"/history-download-jobs/{job['id']}/transition", json=payload)
        self.assertIn("refresh_continuous_aggregate", failed_refresh.exception.statement or "")
        current = (await self.client.get(f"/history-download-jobs/{job['id']}")).json()
        self.assertEqual(current, job)
        self.assertEqual(current["status"], "downloading")
        self.assertEqual(current["inserted_count"], 2)
        async with self.engine.begin() as connection:
            rows_after = (
                (
                    await connection.execute(
                        select(candles)
                        .where(candles.c.symbol_id == self.market_id)
                        .order_by(candles.c.timestamp_utc)
                    )
                )
                .mappings()
                .all()
            )
            self.assertEqual(rows_after, rows_before)
            await connection.execute(text("""
                CREATE OR REPLACE FUNCTION fail_download_refresh(value DOUBLE PRECISION)
                RETURNS DOUBLE PRECISION LANGUAGE plpgsql IMMUTABLE AS $$
                BEGIN
                    RETURN value;
                END;
                $$
            """))
        completed = await self.client.post(
            f"/history-download-jobs/{job['id']}/transition", json=payload
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["inserted_count"], 2)
        async with self.engine.connect() as connection:
            volume = await connection.scalar(
                text(
                    "SELECT volume FROM candles_agg_m5 "
                    "WHERE symbol_id=:id AND bucket=to_timestamp(300)"
                ),
                {"id": self.market_id},
            )
            self.assertEqual(volume, 20)

    async def test_explicit_live_write_holds_market_lock_until_candles_commit(self):
        reached_write = asyncio.Event()
        release_write = asyncio.Event()
        original_insert = crud.insert_candles

        async def blocked_insert(session, market_id, values):
            reached_write.set()
            await release_write.wait()
            return await original_insert(session, market_id, values)

        with patch("main.crud.insert_candles", new=blocked_insert):
            pending = asyncio.create_task(
                self.client.post(
                    "/candles",
                    json=dict(
                        market_id=self.market_id,
                        symbol="EURUSD",
                        exchange="TEST BROKER",
                        candles=[bar(0)],
                    ),
                )
            )
            try:
                await asyncio.wait_for(reached_write.wait(), timeout=5)
                async with self.engine.begin() as connection:
                    await connection.execute(text("SET LOCAL lock_timeout = '100ms'"))
                    with self.assertRaisesRegex(DBAPIError, "lock timeout"):
                        await connection.execute(
                            text("DELETE FROM markets WHERE symbol_id=:id"),
                            {"id": self.market_id},
                        )
            finally:
                release_write.set()
                response = await asyncio.wait_for(pending, timeout=5)
        self.assertEqual(response.status_code, 200, response.text)

    async def test_delayed_live_and_recovery_writes_reject_recreated_market_name(self):
        old_id = self.market_id
        release_writes = asyncio.Event()

        async def delayed_write(path, extra):
            await release_writes.wait()
            return await self.client.post(
                path,
                json=dict(
                    market_id=old_id,
                    symbol="EURUSD",
                    exchange="TEST BROKER",
                    candles=[bar(0, value=2)],
                    **extra,
                ),
            )

        pending = [
            asyncio.create_task(delayed_write("/candles", {})),
            asyncio.create_task(
                delayed_write("/candles/historical", {"start_ms": 0, "end_ms": 59999})
            ),
        ]
        try:
            deleted = await self.client.delete(
                "/markets/EURUSD", params={"exchange": "TEST BROKER"}
            )
            self.assertEqual(deleted.status_code, 200, deleted.text)
            with patch("main.verify_broker_market", new=AsyncMock()):
                created = await self.client.post("/markets", json=SPEC)
            self.assertEqual(created.status_code, 200, created.text)
            new_id = created.json()["symbol_id"]
            self.assertNotEqual(old_id, new_id)
            async with self.engine.begin() as connection:
                await connection.execute(
                    insert(candles).values(
                        symbol_id=new_id,
                        timestamp_utc=datetime.fromtimestamp(0, timezone.utc),
                        open=70,
                        high=80,
                        low=60,
                        close=77,
                        volume=50,
                    )
                )
        finally:
            release_writes.set()
            responses = await asyncio.wait_for(asyncio.gather(*pending), timeout=5)
        self.assertEqual([response.status_code for response in responses], [404, 404])
        async with self.engine.connect() as connection:
            rows = (
                (await connection.execute(select(candles).where(candles.c.symbol_id == new_id)))
                .mappings()
                .all()
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["close"], 77)
