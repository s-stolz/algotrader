"""Run one real worker in an isolated acceptance-test subprocess."""

import asyncio
import sys
from typing import cast
from unittest.mock import AsyncMock

from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.store import HistoryStore
from app.history.worker import HistoryWorker
from db_accessor_client import AsyncDatabaseAccessorClient


async def run():
    accessor_url, broker_url, job_id = sys.argv[1:]
    store = AsyncDatabaseAccessorClient()
    store.base_url = accessor_url
    job = await store.get_history_download_job(job_id)
    source = job["source_snapshot"]
    broker = BrokerClient(broker_url, source["broker_account_id"])
    try:
        worker = HistoryWorker(
            cast(HistoryStore, store),
            broker,
            HistoryEvents(AsyncMock()),
            source["broker_account_id"],
            source["broker_environment"],
            asyncio.Semaphore(1),
        )
        await worker.run(job_id)
    finally:
        await broker.aclose()
        await store.aclose()


if __name__ == "__main__":
    asyncio.run(run())
