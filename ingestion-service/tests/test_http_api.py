import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.service import HistoryDownloads
from app.history.store import HistoryStore
from app.http_api import create_app
from main import IngestionService

from tests.history.fakes import Broker, Store, job


class HistoryApiTests(unittest.IsolatedAsyncioTestCase):
    def service(self, store, broker):
        history = HistoryDownloads(
            cast(HistoryStore, store),
            cast(BrokerClient, broker),
            HistoryEvents(AsyncMock()),
            "12345",
            "demo",
            1,
            asyncio.Semaphore(1),
        )
        ready = asyncio.Event()
        ready.set()
        service = SimpleNamespace(history=history, ready=ready, _shutdown=False)
        return cast(IngestionService, service)

    async def test_accepted_request_continues_after_browser_closes(self):
        store, broker = Store(job(end=180_000)), Broker([60_000, 120_000])
        service = self.service(store, broker)
        identity = str(uuid4())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url="http://test"
        ) as browser:
            response = await browser.post(
                "/history-downloads",
                json={
                    "request_id": identity,
                    "market_id": 1,
                    "candle_count": 1,
                },
            )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("owner_token", response.json())
        assert service.history is not None
        worker = asyncio.create_task(service.history.run())
        try:
            async with asyncio.timeout(2):
                while store.job["status"] != "completed":
                    await asyncio.sleep(0.01)
            self.assertEqual(sorted(store.rows), [120_000])
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    async def test_custom_market_cannot_request_broker_history(self):
        store, broker = Store(job()), Broker()
        store.market["source_type"] = "custom"
        service = self.service(store, broker)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url="http://test"
        ) as browser:
            response = await browser.post(
                "/history-downloads",
                json={
                    "request_id": str(uuid4()),
                    "market_id": 1,
                    "candle_count": 10,
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Custom", response.json()["detail"])
        self.assertFalse(broker.requests)

    async def test_invalid_selector_and_count_are_rejected(self):
        service = self.service(Store(job()), Broker())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url="http://test"
        ) as browser:
            for selector in (
                {},
                {"candle_count": True},
                {"candle_count": 1_000_001},
                {"start_date": "1969-01-01"},
                {"start_date": "2020-01-01", "candle_count": 1},
            ):
                response = await browser.post(
                    "/history-downloads",
                    json={
                        "request_id": str(uuid4()),
                        "market_id": 1,
                        **selector,
                    },
                )
                self.assertEqual(response.status_code, 422)

    async def test_cancel_returns_terminal_state_and_preserves_downloaded_rows(self):
        store, broker = Store(job()), Broker()
        store.rows[60_000] = {"close": 7}
        service = self.service(store, broker)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url="http://test"
        ) as browser:
            response = await browser.post(f"/history-downloads/{store.job['id']}/cancel")
            listed = await browser.get("/history-downloads", params={"market_id": 1})
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertEqual(listed.json()[0]["status"], "cancelled")
        self.assertEqual(store.rows[60_000]["close"], 7)

    async def test_starting_service_is_not_ready_and_does_not_accept_work(self):
        service = self.service(Store(job()), Broker())
        service.ready.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url="http://test"
        ) as browser:
            self.assertEqual((await browser.get("/health")).status_code, 503)
            response = await browser.post(
                "/history-downloads",
                json={
                    "request_id": str(uuid4()),
                    "market_id": 1,
                    "candle_count": 10,
                },
            )
            self.assertEqual(response.status_code, 503)
