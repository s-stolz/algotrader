import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from app import market_cache
from app.database import get_db
from app.models import candles, markets
from app.models import history_download_jobs as jobs
from main import app
from sqlalchemy import create_engine, insert, select, update
from test_market_editing import Session
from test_market_sources import BINDING


def candle(timestamp, close=2):
    return dict(timestamp_ms=timestamp, open=1, high=3, low=1, close=close, volume=5)


class DownloadStorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for table in (markets, candles, jobs):
            table.create(self.engine)
        self.connection = self.engine.connect()
        self.session = StorageSession(self.connection)

        async def database():
            yield self.session

        app.dependency_overrides[get_db] = database
        market_cache._rebuild_cache([])
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.spec = dict(
            symbol="EURUSD",
            exchange="IC TRADING",
            market_type="Forex",
            min_move=0.00001,
            timezone="UTC",
            settlement_currency="USD",
            contract_multiplier=1,
            minimum_quantity=1,
            quantity_step=1,
        )
        with patch("main.verify_broker_market", new=AsyncMock()):
            response = await self.client.post("/markets", json={**self.spec, **BINDING})
        response.raise_for_status()
        self.market_id = response.json()["symbol_id"]
        self.connection.execute(
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
        self.connection.commit()

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        market_cache._rebuild_cache([])
        self.connection.close()
        self.engine.dispose()

    async def accept(self, **selector):
        response = await self.client.post(
            "/history-download-jobs",
            json=dict(
                request_id=str(uuid4()),
                market_id=self.market_id,
                **selector,
            ),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def claim(self, job, owner="worker1"):
        response = await self.client.post(
            f"/history-download-jobs/{job['id']}/claim",
            json=dict(
                owner_token=owner,
                lease_seconds=120,
            ),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def page(self, job, next_ms=300000, bars=None):
        bars = bars if bars is not None else [candle(300000), candle(360000)]
        return await self.client.post(
            f"/history-download-jobs/{job['id']}/pages",
            json=dict(
                owner_token=job["owner_token"],
                revision=job["revision"],
                expected_cursor_ms=job["cursor_ms"],
                next_cursor_ms=next_ms,
                fetched_count=len(bars),
                candles=bars,
            ),
        )

    async def test_accept_freezes_oldest_boundary_and_idempotency(self):
        job = await self.accept(start_ms=0)
        self.assertEqual(job["end_exclusive_ms"], 600000)
        self.assertEqual(job["cursor_ms"], 600000)
        self.assertEqual(job["source_snapshot"]["broker_symbol_id"], 17)
        duplicate = await self.client.post(
            "/history-download-jobs",
            json=dict(
                request_id=job["request_id"],
                market_id=self.market_id,
                start_ms=0,
            ),
        )
        self.assertEqual(duplicate.json(), job)
        for payload in (
            dict(request_id=job["request_id"], market_id=self.market_id, start_ms=60000),
            dict(request_id=str(uuid4()), market_id=self.market_id, candle_count=2),
        ):
            response = await self.client.post("/history-download-jobs", json=payload)
            self.assertEqual(response.status_code, 409, response.text)

    async def test_custom_market_cannot_accept_history(self):
        created = await self.client.post("/markets", json={**self.spec, "exchange": "CSV"})
        response = await self.client.post(
            "/history-download-jobs",
            json=dict(
                request_id=str(uuid4()),
                market_id=created.json()["symbol_id"],
                start_ms=0,
            ),
        )
        self.assertEqual(response.status_code, 409)

    async def test_page_is_atomic_idempotent_and_preserves_existing_values(self):
        job = await self.claim(await self.accept(start_ms=0))
        self.connection.execute(
            insert(candles).values(
                symbol_id=self.market_id,
                timestamp_utc=datetime.fromtimestamp(300, timezone.utc),
                open=10,
                high=30,
                low=10,
                close=20,
                volume=50,
            )
        )
        self.connection.commit()
        response = await self.page(job)
        self.assertEqual(response.status_code, 200, response.text)
        after = response.json()
        self.assertEqual((after["fetched_count"], after["inserted_count"]), (2, 1))
        row = (
            self.connection.execute(
                select(candles).where(
                    candles.c.timestamp_utc == datetime.fromtimestamp(300, timezone.utc)
                )
            )
            .mappings()
            .one()
        )
        self.assertEqual(row["close"], 20)
        self.assertIsNone((await self.page(job)).json())
        stored = (await self.client.get(f"/history-download-jobs/{job['id']}")).json()
        self.assertEqual(stored["inserted_count"], 1)
        self.assertEqual(stored["cursor_ms"], 300000)

    async def test_cancel_fences_writes_and_retry_retains_confirmed_progress(self):
        job = await self.claim(await self.accept(candle_count=5))
        job = (await self.page(job)).json()
        response = await self.client.post(f"/history-download-jobs/{job['id']}/cancel")
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertIsNone((await self.page(job, 0, [candle(60000)])).json())
        retried = (await self.client.post(f"/history-download-jobs/{job['id']}/retry")).json()
        self.assertEqual(retried["status"], "queued")
        self.assertEqual(retried["inserted_count"], 2)
        self.assertEqual(retried["cursor_ms"], 300000)
        claimed = await self.claim(retried, "worker2")
        self.assertGreater(claimed["revision"], job["revision"])

    async def test_expired_owner_cannot_write_after_reclaim(self):
        job = await self.claim(await self.accept(start_ms=0))
        self.connection.execute(
            update(jobs)
            .where(jobs.c.id == job["id"])
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        self.connection.commit()
        newer = await self.claim(job, "worker2")
        self.assertIsNone((await self.page(job)).json())
        self.assertEqual((await self.page(newer)).status_code, 200)

    async def test_delete_is_blocked_until_cancelled(self):
        job = await self.accept(start_ms=0)
        response = await self.client.delete("/markets/EURUSD", params={"exchange": "IC TRADING"})
        self.assertEqual(response.status_code, 409, response.text)
        await self.client.post(f"/history-download-jobs/{job['id']}/cancel")
        response = await self.client.delete("/markets/EURUSD", params={"exchange": "IC TRADING"})
        self.assertEqual(response.status_code, 200, response.text)

    async def test_page_rejects_out_of_range_and_count_overflow_without_writes(self):
        job = await self.claim(await self.accept(candle_count=1))
        response = await self.page(job)
        self.assertEqual(response.status_code, 409)
        response = await self.page(job, bars=[candle(600000)])
        self.assertEqual(response.status_code, 422)
        stored = (await self.client.get(f"/history-download-jobs/{job['id']}")).json()
        self.assertEqual(stored["inserted_count"], 0)
        self.assertEqual(stored["cursor_ms"], 600000)

    async def test_completed_waits_for_aggregate_refresh(self):
        job = await self.claim(await self.accept(candle_count=2))
        job = (await self.page(job)).json()
        path = f"/history-download-jobs/{job['id']}/transition"
        payload = dict(owner_token=job["owner_token"], revision=job["revision"], status="completed")
        with patch(
            "app.history_downloads.aggregates.refresh_inserted_history", new=AsyncMock()
        ) as refresh:
            response = await self.client.post(path, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            refresh.assert_awaited_once()
        self.assertEqual(response.json()["status"], "completed")
        self.assertIsNone(response.json()["owner_token"])

    async def test_refresh_failure_preserves_owner_revision_and_confirmed_raw_pages(self):
        job = await self.claim(await self.accept(candle_count=2))
        job = (await self.page(job)).json()
        rows_before = self.connection.execute(select(candles)).mappings().all()
        payload = dict(owner_token=job["owner_token"], revision=job["revision"], status="completed")
        with patch(
            "app.history_downloads.aggregates.refresh_inserted_history",
            new=AsyncMock(side_effect=RuntimeError("aggregate refresh failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "aggregate refresh failed"):
                await self.client.post(
                    f"/history-download-jobs/{job['id']}/transition", json=payload
                )
        current = (await self.client.get(f"/history-download-jobs/{job['id']}")).json()
        self.assertEqual(current, job)
        self.assertEqual(current["status"], "downloading")
        self.assertEqual(current["inserted_count"], 2)
        self.assertEqual(self.connection.execute(select(candles)).mappings().all(), rows_before)


class StorageSession(Session):
    def get_bind(self):
        return self.connection.engine
