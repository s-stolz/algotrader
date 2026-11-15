import asyncio
import json
import logging
import unittest
from typing import cast
from unittest.mock import AsyncMock

import httpx
from app.broker_client import BrokerClient
from app.history.events import HistoryEvents
from app.history.store import HistoryStore
from app.history.worker import HistoryWorker

from tests.history.fakes import Store, job


class BrokerIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_source_acquisition_and_release_sends_frozen_instrument_id(self):
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path.endswith("trendbars/stream"):
                return httpx.Response(
                    200,
                    text=json.dumps(
                        dict(
                            type="complete",
                            version=1,
                            count=0,
                            fromTs=60000,
                            toTs=119999,
                            limit=None,
                        )
                    ),
                )
            return httpx.Response(200, json={"status": "ok"})

        broker = BrokerClient("http://broker", "account")
        await broker.async_client.aclose()
        broker.async_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            await broker.start_trendbar_stream("EURUSD", expected_symbol_id=17)
            async for _ in broker.stream_trendbars(
                "EURUSD", start_time=60000, end_time=119999, expected_symbol_id=17
            ):
                self.fail("Empty window unexpectedly contained a candle")
            await broker.stop_trendbar_stream("EURUSD", expected_symbol_id=17)
        finally:
            await broker.aclose()
        self.assertEqual(len(requests), 3)
        self.assertTrue(
            all(request.url.params["expected_symbol_id"] == "17" for request in requests)
        )

    async def test_remapped_broker_instrument_rejection_never_writes_history(self):
        store = Store(job(end=180000))
        requested = []

        def remapped(request):
            requested.append(request.url.params.get("expected_symbol_id"))
            return httpx.Response(
                409, json={"detail": "Instrument no longer matches stored binding"}
            )

        broker = BrokerClient("http://broker", "12345")
        await broker.async_client.aclose()
        broker.async_client = httpx.AsyncClient(transport=httpx.MockTransport(remapped))
        worker = HistoryWorker(
            cast(HistoryStore, store),
            broker,
            HistoryEvents(AsyncMock()),
            "12345",
            "demo",
            asyncio.Semaphore(1),
        )
        logging.disable(logging.CRITICAL)
        try:
            await worker.run(store.job["id"])
        finally:
            logging.disable(logging.NOTSET)
            await broker.aclose()
        self.assertEqual(requested, ["11"])
        self.assertEqual(store.job["status"], "failed")
        self.assertEqual(store.job["cursor_ms"], 180000)
        self.assertFalse(store.rows)
