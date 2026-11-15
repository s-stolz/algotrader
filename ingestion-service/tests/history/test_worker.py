import asyncio
import logging
import unittest
from typing import cast
from unittest.mock import AsyncMock, patch

from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.store import HistoryStore
from app.history.worker import WINDOW_MS, HistoryWorker

from tests.history.fakes import Broker, Store, job


class HistoryWorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def worker(self, store, broker):
        return HistoryWorker(
            cast(HistoryStore, store),
            cast(BrokerClient, broker),
            HistoryEvents(AsyncMock()),
            "12345",
            "demo",
            asyncio.Semaphore(1),
        )

    async def test_count_skips_empty_days_and_downloads_latest_actual_candles(self):
        store = Store(job(start_ms=None, candle_count=2))
        broker = Broker([60_000, 120_000, 180_000, 180_000])
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(sorted(store.rows), [120_000, 180_000])
        self.assertEqual(len(broker.requests), 3)
        self.assertEqual(store.job["inserted_count"], 2)
        self.assertEqual(store.job["fetched_count"], 2)
        self.assertIsNone(store.job["availability_reason"])

    async def test_date_includes_boundary_but_excludes_frozen_upper_boundary(self):
        store = Store(job(start_ms=60_000, end=180_000))
        broker = Broker([0, 60_000, 120_000, 180_000])
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(sorted(store.rows), [60_000, 120_000])
        self.assertEqual(store.job["cursor_ms"], 60_000)

    async def test_incomplete_page_never_writes_or_advances_progress(self):
        store = Store(job(end=180_000))
        broker = Broker([60_000])
        broker.fail = True
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "failed")
        self.assertEqual(store.job["cursor_ms"], 180_000)
        self.assertFalse(store.rows)

    async def test_shutdown_requeues_and_restart_resumes_saved_cursor(self):
        store = Store(job())
        broker = Broker([WINDOW_MS + 60_000, 2 * WINDOW_MS + 60_000])
        store.after_commit = broker.gate.clear
        worker = self.worker(store, broker)
        task = asyncio.create_task(worker.run(store.job["id"]))
        async with asyncio.timeout(2):
            while len(broker.requests) < 2:
                await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(store.job["status"], "queued")
        self.assertEqual(store.job["cursor_ms"], 2 * WINDOW_MS)
        self.assertEqual(store.job["inserted_count"], 1)
        store.after_commit = lambda: None
        broker.gate.set()
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(store.job["inserted_count"], 2)

    async def test_cancel_fences_in_flight_page_and_never_requeues(self):
        store = Store(job(end=180_000))
        broker = Broker([60_000])
        broker.gate.clear()
        task = asyncio.create_task(self.worker(store, broker).run(store.job["id"]))
        await broker.entered.wait()
        await store.cancel_history_download_job(store.job["id"])
        broker.gate.set()
        await task
        self.assertEqual(store.job["status"], "cancelled")
        self.assertFalse(store.rows)

    async def test_lost_commit_receipt_keeps_counts_and_retry_does_not_overwrite(self):
        store = Store(job(end=180_000))
        broker = Broker([60_000])

        def lost_receipt():
            raise OSError("response lost after commit")

        store.after_commit = lost_receipt
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["inserted_count"], 1)
        store.rows[60_000]["close"] = 9
        store.after_commit = lambda: None
        await store.retry_history_download_job(store.job["id"])
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(store.job["inserted_count"], 1)
        self.assertEqual(store.rows[60_000]["close"], 9)

    async def test_scan_budget_is_resumable_failure_not_false_exhaustion(self):
        store = Store(job(start_ms=None, candle_count=1))
        broker = Broker([60_000])
        with patch("app.history.worker.MAX_WINDOWS_PER_ATTEMPT", 2):
            await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "failed")
        self.assertEqual(store.job["cursor_ms"], WINDOW_MS)
        self.assertIsNone(store.job["availability_reason"])
        await store.retry_history_download_job(store.job["id"])
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(store.job["inserted_count"], 1)

    async def test_epoch_exhaustion_reports_fewer_available(self):
        store = Store(job(start_ms=None, candle_count=2, end=180_000))
        await self.worker(store, Broker([60_000])).run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(store.job["inserted_count"], 1)
        self.assertIsNotNone(store.job["availability_reason"])

    async def test_mismatched_account_does_not_query_broker(self):
        store = Store(job())
        store.job["source_snapshot"]["broker_account_id"] = "other"
        broker = Broker()
        await self.worker(store, broker).run(store.job["id"])
        self.assertEqual(store.job["status"], "failed")
        self.assertFalse(broker.requests)

    async def test_lost_completion_receipt_still_invalidates_terminal_revision(self):
        store = Store(job(end=180_000))
        store.lose_completion_receipt = True
        worker = self.worker(store, Broker([60_000]))
        await worker.run(store.job["id"])
        self.assertEqual(store.job["status"], "completed")
        self.assertEqual(worker.events.pending[store.job["id"]]["revision"], store.job["revision"])
