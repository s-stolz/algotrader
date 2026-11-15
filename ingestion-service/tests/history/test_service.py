import asyncio
import unittest
from typing import cast
from unittest.mock import AsyncMock

from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.service import HistoryDownloads
from app.history.store import HistoryStore
from db_accessor_client import DatabaseAccessorClientError

from tests.history.fakes import Broker, Store, job


class HistoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_finished_worker_snapshot_is_retried_before_discarding_its_task(self):
        store = Store(job())
        store.job.update(status="completed", revision=7)
        read = AsyncMock(side_effect=[DatabaseAccessorClientError("unavailable"), store.job])
        store.get_history_download_job = read
        redis = AsyncMock()
        events = HistoryEvents(redis)
        service = HistoryDownloads(
            cast(HistoryStore, store),
            cast(BrokerClient, Broker()),
            events,
            "12345",
            "demo",
            1,
            asyncio.Semaphore(1),
        )
        task = asyncio.create_task(asyncio.sleep(0))
        await task
        service.tasks[store.job["id"]] = task
        with self.assertRaises(DatabaseAccessorClientError):
            await service._collect_finished()
        self.assertIn(store.job["id"], service.tasks)
        await service._collect_finished()
        self.assertNotIn(store.job["id"], service.tasks)
        self.assertEqual(events.pending[store.job["id"]]["revision"], 7)
        redis.xadd.side_effect = [OSError("interrupted"), "1-0", "2-0"]
        await events.flush()
        self.assertIn(store.job["id"], events.pending)
        await events.flush()
        self.assertFalse(events.pending)

    async def test_startup_resnapshots_even_when_old_terminal_is_outside_recent_hundred(self):
        store = Store(job())
        store.job.update(status="completed", revision=9)
        recent = [dict(store.job, id=f"unrelated-{index}") for index in range(100)]

        async def list_jobs(market_id=None, active_only=False, limit=50):
            return [] if active_only else recent[:limit]

        store.list_history_download_jobs = list_jobs
        redis = AsyncMock()
        events = HistoryEvents(redis)
        service = HistoryDownloads(
            cast(HistoryStore, store),
            cast(BrokerClient, Broker()),
            events,
            "12345",
            "demo",
            1,
            asyncio.Semaphore(1),
        )
        task = asyncio.create_task(service.run())
        try:
            async with asyncio.timeout(2):
                while redis.xadd.await_count == 0:
                    await asyncio.sleep(0)
            self.assertIn("historyDownloadsResnapshot", redis.xadd.call_args.args[1]["event"])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_lost_queued_cancellation_receipt_resnapshots_without_an_active_worker(self):
        store = Store(job())
        original_cancel = store.cancel_history_download_job

        async def cancel_with_lost_receipt(job_id):
            await original_cancel(job_id)
            raise DatabaseAccessorClientError("Cancellation receipt lost")

        store.cancel_history_download_job = cancel_with_lost_receipt
        redis = AsyncMock()
        events = HistoryEvents(redis)
        await events.flush()
        self.assertFalse(events.resnapshot_pending)
        redis.xadd.reset_mock()
        service = HistoryDownloads(
            cast(HistoryStore, store),
            cast(BrokerClient, Broker()),
            events,
            "12345",
            "demo",
            1,
            asyncio.Semaphore(1),
        )
        with self.assertRaises(DatabaseAccessorClientError):
            await service.cancel(store.job["id"])
        self.assertEqual(store.job["status"], "cancelled")
        self.assertFalse(service.tasks)
        self.assertTrue(events.resnapshot_pending)
        task = asyncio.create_task(service.run())
        try:
            async with asyncio.timeout(2):
                while redis.xadd.await_count == 0:
                    await asyncio.sleep(0)
            self.assertIn("historyDownloadsResnapshot", redis.xadd.call_args.args[1]["event"])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_cancelled_command_await_also_requests_an_authoritative_resnapshot(self):
        store = Store(job())
        store.cancel_history_download_job = AsyncMock(side_effect=asyncio.CancelledError)
        events = HistoryEvents(AsyncMock())
        await events.flush()
        service = HistoryDownloads(
            cast(HistoryStore, store),
            cast(BrokerClient, Broker()),
            events,
            "12345",
            "demo",
            1,
            asyncio.Semaphore(1),
        )
        with self.assertRaises(asyncio.CancelledError):
            await service.cancel(store.job["id"])
        self.assertTrue(events.resnapshot_pending)
