import asyncio
from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.history.worker import WINDOW_MS


def market(**changes):
    return (
        dict(
            symbol_id=1,
            symbol="EURUSD",
            exchange="Broker",
            source_type="broker",
            broker_provider="ctrader",
            broker_account_id="12345",
            broker_environment="demo",
            broker_symbol_id=11,
            live_start_ms=3 * WINDOW_MS,
        )
        | changes
    )


def job(
    *, start_ms: int | None = 0, candle_count: int | None = None, end: int = 3 * WINDOW_MS
) -> dict[str, Any]:
    identity = str(uuid4())
    return dict(
        id=identity,
        request_id=identity,
        market_id=1,
        status="queued",
        start_ms=start_ms,
        candle_count=candle_count,
        end_exclusive_ms=end,
        cursor_ms=end,
        fetched_count=0,
        inserted_count=0,
        source_snapshot=market(),
        owner_token=None,
        revision=1,
        lease_expires_at=None,
        created_at="1970-01-04T00:00:00Z",
        updated_at="1970-01-04T00:00:00Z",
        failure_reason=None,
        availability_reason=None,
    )


class Store:
    def __init__(self, value):
        self.job: dict[str, Any] = deepcopy(value)
        self.rows = {}
        self.pages = []
        self.after_commit = lambda: None
        self.lose_completion_receipt = False
        self.market = market()

    async def get_market_by_id(self, market_id):
        return deepcopy(self.market)

    async def create_history_download_job(self, data):
        self.job.update(data)
        self.job["id"] = data["request_id"]
        return deepcopy(self.job)

    async def get_history_download_job(self, job_id):
        return deepcopy(self.job)

    async def list_history_download_jobs(self, market_id=None, active_only=False, limit=50):
        if active_only and self.job["status"] not in {"queued", "downloading"}:
            return []
        return [deepcopy(self.job)]

    async def claim_history_download_job(self, job_id, owner_token, lease_seconds=120):
        if self.job["status"] != "queued":
            return None
        self.job.update(
            status="downloading", owner_token=owner_token, revision=self.job["revision"] + 1
        )
        return deepcopy(self.job)

    async def heartbeat_history_download_job(
        self, job_id, owner_token, revision, lease_seconds=120
    ):
        if self.job["owner_token"] != owner_token or self.job["revision"] != revision:
            return None
        return deepcopy(self.job)

    def owns(self, data):
        return (
            self.job["status"] == "downloading"
            and data["owner_token"] == self.job["owner_token"]
            and data["revision"] == self.job["revision"]
        )

    async def commit_history_download_page(self, job_id, data):
        if not self.owns(data) or data["expected_cursor_ms"] != self.job["cursor_ms"]:
            return None
        self.pages.append(deepcopy(data))
        added = 0
        for candle in data["candles"]:
            if candle["timestamp_ms"] not in self.rows:
                self.rows[candle["timestamp_ms"]] = candle
                added += 1
        self.job["inserted_count"] += added
        self.job["fetched_count"] += data["fetched_count"]
        self.job["cursor_ms"] = data["next_cursor_ms"]
        self.job["revision"] += 1
        self.after_commit()
        return deepcopy(self.job)

    async def transition_history_download_job(self, job_id, data):
        if not self.owns(data):
            return None
        self.job.update(
            status=data["status"],
            owner_token=None,
            revision=self.job["revision"] + 1,
            failure_reason=data.get("failure_reason"),
            availability_reason=data.get("availability_reason"),
        )
        if data["status"] == "completed" and self.lose_completion_receipt:
            self.lose_completion_receipt = False
            raise OSError("completion receipt lost")
        return deepcopy(self.job)

    async def cancel_history_download_job(self, job_id):
        self.job.update(status="cancelled", owner_token=None, revision=self.job["revision"] + 1)
        return deepcopy(self.job)

    async def retry_history_download_job(self, job_id):
        self.job.update(status="queued", revision=self.job["revision"] + 1)
        return deepcopy(self.job)


class Broker:
    def __init__(self, timestamps=()):
        self.timestamps = timestamps
        self.requests = []
        self.gate = asyncio.Event()
        self.gate.set()
        self.entered = asyncio.Event()
        self.fail = False

    async def stream_trendbars(
        self, symbol, *, timeframe, start_time, end_time, expected_symbol_id=None
    ):
        self.requests.append((start_time, end_time))
        self.entered.set()
        await self.gate.wait()
        for timestamp in self.timestamps:
            if start_time <= timestamp <= end_time:
                yield dict(t=timestamp, o=1, h=2, l=0, c=1, v=10)
        if self.fail:
            raise RuntimeError("incomplete historical delivery")
