from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger("ingestion-service.history.events")
EVENT_STREAM = "history:downloads:events"


class HistoryEvents:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.pending: dict[str, dict[str, Any]] = {}
        self.connected = False
        self.resnapshot_pending = True

    def changed(self, job: dict[str, Any]) -> None:
        event = {
            "type": "historyDownloadChanged",
            "market_id": job["market_id"],
            "job_id": job["id"],
            "revision": job["revision"],
        }
        previous = self.pending.get(job["id"])
        if previous is None or previous["revision"] < event["revision"]:
            self.pending[job["id"]] = event

    def request_resnapshot(self) -> None:
        self.resnapshot_pending = True

    async def flush(self) -> None:
        if self.resnapshot_pending:
            try:
                await self.redis.xadd(
                    EVENT_STREAM,
                    {"event": json.dumps({"type": "historyDownloadsResnapshot"})},
                    maxlen=10000,
                    approximate=True,
                )
            except Exception:
                self.connected = False
                logger.warning("History notifications unavailable; resnapshot retained")
                return
            self.connected = True
            self.resnapshot_pending = False
        for job_id, event in list(self.pending.items()):
            try:
                await self.redis.xadd(
                    EVENT_STREAM, {"event": json.dumps(event)}, maxlen=10000, approximate=True
                )
            except Exception:
                self.connected = False
                self.request_resnapshot()
                logger.warning("History notifications unavailable; pending changes retained")
                return
            self.connected = True
            if self.pending.get(job_id) == event:
                del self.pending[job_id]
