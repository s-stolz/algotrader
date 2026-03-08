"""Unit tests for the shared db accessor clients."""

import unittest

import httpx
from db_accessor_client import (
    AsyncDatabaseAccessorClient,
    DatabaseAccessorClient,
    DatabaseAccessorClientError,
)


class DatabaseAccessorClientTests(unittest.TestCase):
    def test_get_markets_passes_query_params(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/markets")
            self.assertEqual(request.url.params.get("symbol"), "EURUSD")
            self.assertIsNone(request.url.params.get("exchange"))
            return httpx.Response(200, json=[{"symbol_id": 1, "symbol": "EURUSD"}])

        client = DatabaseAccessorClient("http://test")
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            markets = client.get_markets(symbol="EURUSD")
        finally:
            client.close()
        self.assertEqual(markets[0]["symbol_id"], 1)

    def test_get_latest_candle_returns_none_for_empty_list(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        client = DatabaseAccessorClient("http://test")
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            latest = client.get_latest_candle(symbol_id=1, timeframe="M1")
        finally:
            client.close()
        self.assertIsNone(latest)

    def test_insert_candles_raises_client_error_on_http_failure(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        client = DatabaseAccessorClient("http://test")
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError):
                client.insert_candles(symbol_id=1, candles=[])
        finally:
            client.close()


class AsyncDatabaseAccessorClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_get_candles_returns_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/candles/7")
            self.assertEqual(request.url.params.get("timeframe"), "M1")
            self.assertEqual(request.url.params.get("limit"), "10")
            return httpx.Response(200, json=[{"timestamp_ms": 1000, "open": 1.0}])

        client = AsyncDatabaseAccessorClient("http://test")
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            candles = await client.get_candles(symbol_id=7, timeframe="M1", limit=10)
        finally:
            await client.aclose()
        self.assertEqual(candles[0]["timestamp_ms"], 1000)
