"""Unit tests for the shared db accessor clients."""

import os
import unittest
from unittest.mock import patch

import httpx
import pandas as pd
from db_accessor_client import (
    AsyncDatabaseAccessorClient,
    DatabaseAccessorClient,
    DatabaseAccessorClientError,
)


class DatabaseAccessorClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patcher = patch.dict(
            os.environ,
            {
                "DATABASE_ACCESSOR_HOST": "test",
                "DATABASE_ACCESSOR_PORT": "80",
            },
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()

    def test_get_markets_passes_query_params(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/markets")
            self.assertEqual(request.url.params.get("symbol"), "EURUSD")
            self.assertIsNone(request.url.params.get("exchange"))
            return httpx.Response(200, json=[{"symbol_id": 1, "symbol": "EURUSD"}])

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            markets = client.get_markets(symbol="EURUSD")
        finally:
            client.close()
        self.assertEqual(markets[0]["symbol_id"], 1)

    def test_get_latest_candle_m1_uses_latest_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD/latest")
            return httpx.Response(200, json={"timestamp_ms": 1000, "open": 1.0})

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            latest = client.get_latest_candle(symbol="EURUSD", timeframe="M1")
        finally:
            client.close()
        if latest is None:
            self.fail("Expected latest candle, got None")
        self.assertEqual(latest["timestamp_ms"], 1000)

    def test_get_latest_candle_m1_returns_none_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD/latest")
            return httpx.Response(404, json={"detail": "No candles found"})

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            latest = client.get_latest_candle(symbol="EURUSD", timeframe="M1")
        finally:
            client.close()
        self.assertIsNone(latest)

    def test_get_latest_m1_candle_uses_latest_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD/latest")
            return httpx.Response(200, json={"timestamp_ms": 999, "open": 1.1})

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            latest = client.get_latest_m1_candle(symbol="EURUSD")
        finally:
            client.close()

        if latest is None:
            self.fail("Expected latest candle, got None")
        self.assertEqual(latest["timestamp_ms"], 999)

    def test_insert_candles_raises_client_error_on_http_failure(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError):
                client.insert_candles(symbol="EURUSD", candles=[])
        finally:
            client.close()

    def test_get_candles_multi_returns_dataframes(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params.get("timeframe"), "M1")
            symbol = request.url.path.split("/")[-1]
            if symbol == "EURUSD":
                return httpx.Response(200, json=[{"timestamp_ms": 1000, "open": 1.0}])
            if symbol == "GBPUSD":
                return httpx.Response(200, json=[{"timestamp_ms": 2000, "open": 2.0}])
            return httpx.Response(404, text="not found")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            frames = client.get_candles_multi(symbols=["EURUSD", "GBPUSD"], timeframe="M1", limit=1)
        finally:
            client.close()

        self.assertIsInstance(frames["EURUSD"], pd.DataFrame)
        self.assertEqual(frames["EURUSD"].iloc[0]["open"], 1.0)
        self.assertEqual(frames["GBPUSD"].iloc[0]["open"], 2.0)
        self.assertNotIn("timestamp_ms", frames["EURUSD"].columns)


class AsyncDatabaseAccessorClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._env_patcher = patch.dict(
            os.environ,
            {
                "DATABASE_ACCESSOR_HOST": "test",
                "DATABASE_ACCESSOR_PORT": "80",
            },
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()

    async def test_async_get_candles_returns_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD")
            self.assertEqual(request.url.params.get("timeframe"), "M1")
            self.assertEqual(request.url.params.get("limit"), "10")
            return httpx.Response(200, json=[{"timestamp_ms": 1000, "open": 1.0}])

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            candles = await client.get_candles(
                symbol="EURUSD", timeframe="M1", limit=10, include_timestamp_ms=True
            )
        finally:
            await client.aclose()
        self.assertIsInstance(candles, pd.DataFrame)
        self.assertEqual(candles.iloc[0]["timestamp_ms"], 1000)

    async def test_async_get_latest_candle_m1_uses_latest_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD/latest")
            return httpx.Response(200, json={"timestamp_ms": 1234, "open": 1.2})

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            latest = await client.get_latest_candle(symbol="EURUSD", timeframe="M1")
        finally:
            await client.aclose()

        if latest is None:
            self.fail("Expected latest candle, got None")
        self.assertEqual(latest["timestamp_ms"], 1234)

    async def test_async_get_latest_m1_candle_uses_latest_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/EURUSD/latest")
            return httpx.Response(200, json={"timestamp_ms": 5678, "open": 1.3})

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            latest = await client.get_latest_m1_candle(symbol="EURUSD")
        finally:
            await client.aclose()

        if latest is None:
            self.fail("Expected latest candle, got None")
        self.assertEqual(latest["timestamp_ms"], 5678)

    async def test_async_get_candles_multi_returns_dataframes(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params.get("timeframe"), "M1")
            symbol = request.url.path.split("/")[-1]
            if symbol == "USDJPY":
                return httpx.Response(200, json=[{"timestamp_ms": 3000, "open": 3.0}])
            if symbol == "AUDUSD":
                return httpx.Response(200, json=[{"timestamp_ms": 4000, "open": 4.0}])
            return httpx.Response(404, text="not found")

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            frames = await client.get_candles_multi(
                symbols=["USDJPY", "AUDUSD"], timeframe="M1", limit=1
            )
        finally:
            await client.aclose()

        self.assertIsInstance(frames["USDJPY"], pd.DataFrame)
        self.assertEqual(frames["USDJPY"].iloc[0]["open"], 3.0)
        self.assertEqual(frames["AUDUSD"].iloc[0]["open"], 4.0)
