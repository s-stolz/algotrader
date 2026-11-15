from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any, TypeVar
from uuid import uuid4

from db_accessor_client.market_sources import require_broker_market

from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.store import HistoryStore, Job

logger = logging.getLogger("ingestion-service.history.worker")
T = TypeVar("T")
MINUTE_MS = 60_000
WINDOW_MS = 24 * 60 * MINUTE_MS
MAX_WINDOWS_PER_ATTEMPT = 3660


class HistoryWorker:
    def __init__(
        self,
        store: HistoryStore,
        broker: BrokerClient,
        events: HistoryEvents,
        account_id: str,
        environment: str,
        capacity: asyncio.Semaphore,
    ):
        self.store = store
        self.broker = broker
        self.events = events
        self.account_id = account_id
        self.environment = environment
        self.capacity = capacity
        self.owner_token = uuid4().hex

    async def run(self, job_id: str) -> None:
        job = await self.store.claim_history_download_job(job_id, self.owner_token)
        if job is None:
            return
        self.events.changed(job)
        try:
            await self._execute(job)
        except asyncio.CancelledError:
            await self._release(job_id)
            raise
        except Exception:
            logger.exception("Historical download failed job=%s", job_id)
            try:
                current = await self.store.get_history_download_job(job_id)
                self.events.changed(current)
                if self._owns(current):
                    await self._transition(
                        current,
                        "failed",
                        failure=(
                            "Historical download failed. Retry to continue from saved progress."
                        ),
                    )
            except Exception:
                logger.exception(
                    "Could not settle failed history job=%s; lease will expire", job_id
                )

    async def _execute(self, job: Job) -> None:
        job_id = job["id"]
        source = require_broker_market(
            job["source_snapshot"] | {"symbol_id": job["market_id"]},
            self.account_id,
            self.environment,
        )
        for _ in range(MAX_WINDOWS_PER_ATTEMPT):
            job = await self.store.get_history_download_job(job_id)
            if not self._owns(job):
                return
            if self._finished(job):
                await self._transition(job, "completed", availability=self._availability(job))
                return
            updated = await self._with_heartbeat(job_id, self._download_page(job, source))
            if updated is None:
                self.events.changed(await self.store.get_history_download_job(job_id))
                return
            job = updated
            self.events.changed(job)
            await asyncio.sleep(0)
        if self._finished(job):
            await self._transition(job, "completed", availability=self._availability(job))
        else:
            await self._transition(
                job,
                "failed",
                failure=(
                    "Reached the history search limit for this attempt. "
                    "Retry to continue farther back from saved progress."
                ),
            )

    def _owns(self, job: Job) -> bool:
        return job["status"] == "downloading" and job["owner_token"] == self.owner_token

    @staticmethod
    def _finished(job: Job) -> bool:
        if job["candle_count"] is not None and job["inserted_count"] >= job["candle_count"]:
            return True
        return job["cursor_ms"] <= (job["start_ms"] or 0)

    @staticmethod
    def _availability(job: Job) -> str | None:
        if job["candle_count"] is not None and job["inserted_count"] < job["candle_count"]:
            return "Fewer candles were available in broker history back to 1970-01-01."
        return None

    async def _download_page(self, job: Job, source: Job) -> Job | None:
        end = job["cursor_ms"]
        start = max(job["start_ms"] or 0, end - WINDOW_MS)
        candles: dict[int, dict[str, Any]] = {}
        async with self.capacity:
            async for raw in self.broker.stream_trendbars(
                source["symbol"], timeframe="M1", start_time=start, end_time=end - 1
            ):
                timestamp = int(raw["t"])
                if not start <= timestamp < end or timestamp % MINUTE_MS:
                    raise ValueError("Broker returned a candle outside the closed M1 request")
                if len(candles) > WINDOW_MS // MINUTE_MS:
                    raise ValueError("Broker returned too many candles for a daily window")
                candles[timestamp] = {
                    "timestamp_ms": timestamp,
                    "open": raw["o"],
                    "high": raw["h"],
                    "low": raw["l"],
                    "close": raw["c"],
                    "volume": raw["v"],
                }
        selected = sorted(candles.values(), key=lambda candle: candle["timestamp_ms"], reverse=True)
        if job["candle_count"] is not None:
            remaining = job["candle_count"] - job["inserted_count"]
            if len(selected) > remaining:
                selected = selected[:remaining]
                start = selected[-1]["timestamp_ms"]
        return await self.store.commit_history_download_page(
            job["id"],
            {
                "owner_token": self.owner_token,
                "revision": job["revision"],
                "expected_cursor_ms": end,
                "next_cursor_ms": start,
                "candles": selected,
                "fetched_count": len(selected),
            },
        )

    async def _with_heartbeat(self, job_id: str, operation: Awaitable[T]) -> T:
        task = asyncio.ensure_future(operation)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=30)
                if done:
                    return task.result()
                current = await self.store.get_history_download_job(job_id)
                if not self._owns(current):
                    task.cancel()
                    raise asyncio.CancelledError
                extended = await self.store.heartbeat_history_download_job(
                    job_id, self.owner_token, current["revision"]
                )
                if extended is None:
                    task.cancel()
                    raise asyncio.CancelledError
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _transition(
        self, job: Job, status: str, *, failure: str | None = None, availability: str | None = None
    ) -> None:
        changed = await self.store.transition_history_download_job(
            job["id"],
            {
                "owner_token": self.owner_token,
                "revision": job["revision"],
                "status": status,
                "failure_reason": failure,
                "availability_reason": availability,
            },
        )
        if changed is None:
            changed = await self.store.get_history_download_job(job["id"])
        self.events.changed(changed)

    async def _release(self, job_id: str) -> None:
        try:
            async with asyncio.timeout(5):
                current = await self.store.get_history_download_job(job_id)
                if self._owns(current):
                    await self._transition(current, "queued")
        except Exception:
            logger.warning("Interrupted history job=%s retains its recoverable lease", job_id)
