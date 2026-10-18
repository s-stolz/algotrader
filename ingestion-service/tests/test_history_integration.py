"""Opt-in ingestion acceptance against an isolated accessor backed by Timescale."""

import json
import os
import unittest
from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from db_accessor_client import DatabaseAccessorClientError
from main import IngestionService

ACCESSOR_URL = os.getenv("HISTORY_TEST_ACCESSOR_URL")
BOUNDARY = 1791158400000  # October 5, 2026 UTC
RESUMED = 1792281600000  # October 18, 2026 UTC
NOW = RESUMED + 180000


def compact(timestamp, value):
    return dict(t=timestamp, o=value, h=value + 2, l=value - 1, c=value + 1, v=value * 10)


class UncertainHistoryTransport(httpx.BaseTransport):
    def __init__(self):
        self.delegate = httpx.HTTPTransport()
        self.calls = 0

    def handle_request(self, request):
        response = self.delegate.handle_request(request)
        if request.url.path == "/candles/historical":
            self.calls += 1
            if self.calls == 2:
                # Commit happened; the HTTP receipt is lost. Replay must correct safely.
                response.read()
                response.close()
                return httpx.Response(503, text="receipt lost", request=request)
        return response

    def close(self):
        self.delegate.close()


@unittest.skipUnless(ACCESSOR_URL, "Set HISTORY_TEST_ACCESSOR_URL for live ingestion acceptance")
class HistoricalIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        assert ACCESSOR_URL is not None
        if urlsplit(ACCESSOR_URL).hostname not in ("127.0.0.1", "localhost"):
            raise RuntimeError("Use a disposable local accessor for history acceptance")
        self.symbol = "V9" + uuid4().hex[:8].upper()
        self.http = httpx.AsyncClient(base_url=ACCESSOR_URL)
        response = await self.http.post(
            "/markets",
            json={
                "symbol": self.symbol,
                "exchange": "VIBE9",
                "market_type": "test",
                "min_move": 0.01,
            },
        )
        response.raise_for_status()
        self.symbol_id = response.json()["symbol_id"]
        with patch.object(IngestionService, "_utc_now_ms", return_value=NOW):
            self.service = IngestionService()
        self.service.db_client._client.base_url = ACCESSOR_URL
        # Avoid unrelated configured Markets and use the actual startup Market loading path.
        self.service.db_client.get_markets = lambda: [
            {"symbol_id": self.symbol_id, "symbol": self.symbol, "exchange": "VIBE9"}
        ]
        redis = Mock()
        from unittest.mock import AsyncMock

        redis.ping = AsyncMock()
        with patch("main.Redis.from_url", return_value=redis):
            await self.service.startup()
        # This suite isolates authoritative history writes; durable startup is
        # exercised separately by test_recovery and the process restart suite.
        for state in self.service.runtime_states:
            state.live_boundary_ms = BOUNDARY
            state.live_ready.set()
        await self.service.write_candles_callback(self.symbol_id, [compact(BOUNDARY, 1)])
        self.requests = []
        self.complete = True

        def history(request):
            self.requests.append(request)
            bars = [compact(BOUNDARY, 8), compact(BOUNDARY + 60000, 9), compact(RESUMED, 7)]
            start, end = int(request.url.params["fromTs"]), int(request.url.params["toTs"])
            records: list[dict[str, Any]] = [bar for bar in bars if start <= bar["t"] <= end]
            if self.complete:
                records.append(
                    dict(
                        type="complete",
                        version=1,
                        count=len(records),
                        limit=None,
                        fromTs=int(request.url.params["fromTs"]),
                        toTs=int(request.url.params["toTs"]),
                    )
                )
            return httpx.Response(200, text="\n".join(json.dumps(r) for r in records))

        await self.service.broker_client.async_client.aclose()
        self.service.broker_client.async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(history)
        )

    async def asyncTearDown(self):
        self.service.db_client.close()
        self.service.broker_client.close()
        await self.service.broker_client.aclose()
        response = await self.http.delete(f"/markets/{self.symbol}", params={"exchange": "VIBE9"})
        response.raise_for_status()
        await self.http.aclose()

    async def stored(self):
        response = await self.http.get(
            f"/candles/{self.symbol}", params={"exchange": "VIBE9", "timeframe": "M1"}
        )
        response.raise_for_status()
        return response.json()

    async def test_boundary_overlap_completed_download_and_uncertain_persistence_replay(self):
        service = self.service
        watermarks = {self.symbol_id: service._get_frozen_watermark(self.symbol, "VIBE9")}
        self.assertEqual(watermarks, {self.symbol_id: BOUNDARY})
        await service.write_candles_callback(self.symbol_id, [compact(RESUMED, 1)])
        service.db_client._client.client.close()
        service.db_client._client.client = httpx.Client(transport=UncertainHistoryTransport())
        chunks = patch.object(service, "CHUNK_SIZE", 1)
        chunks.start()
        self.addCleanup(chunks.stop)
        with patch.object(IngestionService, "_utc_now_ms", return_value=NOW):
            with self.assertRaises(DatabaseAccessorClientError):
                await service._backfill_symbol(
                    self.symbol_id, self.symbol, watermarks[self.symbol_id], NOW
                )
            self.assertEqual(watermarks[self.symbol_id], BOUNDARY)
            await service._backfill_symbol(
                self.symbol_id, self.symbol, watermarks[self.symbol_id], NOW
            )
        await service.write_candles_callback(
            self.symbol_id, [compact(BOUNDARY, 1), compact(RESUMED, 1)]
        )
        rows = await self.stored()
        self.assertEqual([r["timestamp_ms"] for r in rows], [BOUNDARY, BOUNDARY + 60000, RESUMED])
        self.assertEqual([r["close"] for r in rows], [9, 10, 8])
        self.assertEqual(int(self.requests[0].url.params["fromTs"]), BOUNDARY)
        self.assertTrue(all(int(r.url.params["toTs"]) < NOW for r in self.requests))
        self.assertTrue(
            all(
                int(r.url.params["toTs"]) - int(r.url.params["fromTs"]) < 86400000
                for r in self.requests
            )
        )

    async def test_incomplete_download_propagates_without_persisting_partial_history(self):
        self.complete = False
        watermarks = {self.symbol_id: self.service._get_frozen_watermark(self.symbol, "VIBE9")}
        with patch.object(IngestionService, "_utc_now_ms", return_value=NOW):
            with self.assertRaises(RuntimeError):
                await self.service._backfill_symbol(
                    self.symbol_id, self.symbol, watermarks[self.symbol_id], NOW
                )
        self.assertEqual([r["close"] for r in await self.stored()], [2])
        self.complete = True
        with patch.object(IngestionService, "_utc_now_ms", return_value=NOW):
            await self.service._backfill_symbol(
                self.symbol_id, self.symbol, watermarks[self.symbol_id], NOW
            )
        self.assertEqual([r["close"] for r in await self.stored()], [9, 10, 8])
