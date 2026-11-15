from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

from db_accessor_client import DatabaseAccessorClientError
from db_accessor_client.market_sources import require_broker_market

from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.models import HistoryRequest
from app.history.store import HistoryStore, Job
from app.history.worker import HistoryWorker

logger = logging.getLogger("ingestion-service.history.service")


class HistoryDownloads:
    def __init__(
        self,
        store: HistoryStore,
        broker: BrokerClient,
        events: HistoryEvents,
        account_id: str,
        environment: str,
        concurrency: int,
        capacity: asyncio.Semaphore,
    ):
        self.store = store
        self.broker = broker
        self.events = events
        self.account_id = account_id
        self.environment = environment
        self.concurrency = max(1, concurrency)
        self.capacity = capacity
        self.tasks: dict[str, asyncio.Task] = {}
        self.stopping = False
        self.revisions: dict[str, int] = {}

    async def create(self, request: HistoryRequest) -> Job:
        market = await self.store.get_market_by_id(request.market_id)
        require_broker_market(market, self.account_id, self.environment)
        return await self._mutate(self.store.create_history_download_job(request.storage_payload()))

    async def cancel(self, job_id: str) -> Job:
        job = await self._mutate(self.store.cancel_history_download_job(job_id))
        task = self.tasks.get(job_id)
        if task is not None:
            task.cancel()
        return job

    async def retry(self, job_id: str) -> Job:
        previous = await self.store.get_history_download_job(job_id)
        market = await self.store.get_market_by_id(previous["market_id"])
        require_broker_market(market, self.account_id, self.environment)
        return await self._mutate(self.store.retry_history_download_job(job_id))

    async def _mutate(self, operation: Awaitable[Job]) -> Job:
        try:
            changed = await operation
        except (DatabaseAccessorClientError, asyncio.CancelledError):
            self.events.request_resnapshot()
            raise
        self.events.changed(changed)
        return changed

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    await self._collect_finished()
                    jobs = await self.store.list_history_download_jobs(active_only=True, limit=100)
                    self._schedule(jobs)
                    await self.events.flush()
                except Exception:
                    logger.exception("History queue unavailable; durable work remains pending")
                    self.events.request_resnapshot()
                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def _collect_finished(self) -> None:
        for job_id, task in list(self.tasks.items()):
            if not task.done():
                continue
            if not task.cancelled() and task.exception() is not None:
                logger.error("History worker failed job=%s: %s", job_id, task.exception())
            try:
                self.events.changed(await self.store.get_history_download_job(job_id))
            except DatabaseAccessorClientError as exc:
                if exc.status_code != 404:
                    raise
            del self.tasks[job_id]

    def _schedule(self, jobs: list[Job]) -> None:
        for job in jobs:
            if self.revisions.get(job["id"]) != job["revision"]:
                self.events.changed(job)
                self.revisions[job["id"]] = job["revision"]
            if len(self.tasks) >= self.concurrency:
                break
            if job["id"] not in self.tasks:
                worker = HistoryWorker(
                    self.store,
                    self.broker,
                    self.events,
                    self.account_id,
                    self.environment,
                    self.capacity,
                )
                self.tasks[job["id"]] = asyncio.create_task(worker.run(job["id"]))

    async def stop(self) -> None:
        self.stopping = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        await self.events.flush()

    def health(self) -> dict[str, Any]:
        return {"running": not self.stopping, "active_downloads": len(self.tasks)}
