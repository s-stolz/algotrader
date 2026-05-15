"""Unit tests for the shared db accessor clients."""

import json
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


def _backtest_summary_payload() -> dict:
    return {
        "execution_duration_ms": 125,
        "symbol": "EURUSD",
        "timeframe": "M1",
        "engine": "vectorized",
        "strategy_id": "ema-cross",
        "start_ms": 1714521600000,
        "end_ms": 1714608000000,
        "initial_capital": 10000.0,
        "final_equity": 10450.25,
        "final_cash": 9450.25,
        "final_position_symbol": "EURUSD",
        "final_position_quantity": 1000.0,
        "total_return_pct": 4.5025,
        "max_drawdown_pct": 1.25,
        "trade_count": 3,
    }


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

    def test_store_backtest_run_summary_posts_payload(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(
                201,
                json={
                    **payload,
                    "run_id": "run-123",
                    "persisted_at": "2026-05-15T12:34:56Z",
                },
            )

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            summary = client.store_backtest_run_summary(payload)
        finally:
            client.close()

        self.assertEqual(summary["run_id"], "run-123")
        self.assertEqual(summary["start_ms"], 1714521600000)
        self.assertEqual(summary["end_ms"], 1714608000000)

    def test_list_backtest_run_summaries_passes_filters(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(
                dict(request.url.params),
                {
                    "symbol": "EURUSD",
                    "timeframe": "M1",
                    "strategy_id": "ema-cross",
                    "engine": "vectorized",
                },
            )
            return httpx.Response(
                200,
                json=[
                    {
                        **payload,
                        "run_id": "run-123",
                        "persisted_at": "2026-05-15T12:34:56Z",
                    }
                ],
            )

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            summaries = client.list_backtest_run_summaries(
                symbol="EURUSD",
                timeframe="M1",
                strategy_id="ema-cross",
                engine="vectorized",
            )
        finally:
            client.close()

        self.assertEqual(summaries[0]["run_id"], "run-123")
        self.assertEqual(summaries[0]["start_ms"], 1714521600000)
        self.assertNotIn("trades", summaries[0])

    def test_get_backtest_run_summary_uses_run_id(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests/run-123")
            return httpx.Response(
                200,
                json={
                    **payload,
                    "run_id": "run-123",
                    "persisted_at": "2026-05-15T12:34:56Z",
                },
            )

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            summary = client.get_backtest_run_summary("run-123")
        finally:
            client.close()

        self.assertEqual(summary["run_id"], "run-123")
        self.assertEqual(summary["end_ms"], 1714608000000)

    def test_backtest_run_summary_methods_raise_client_error_on_http_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests/run-missing")
            return httpx.Response(404, text="missing")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                client.get_backtest_run_summary("run-missing")
        finally:
            client.close()

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.response_text, "missing")

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

    async def test_async_store_backtest_run_summary_posts_payload(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(
                201,
                json={
                    **payload,
                    "run_id": "run-async-123",
                    "persisted_at": "2026-05-15T12:34:56Z",
                },
            )

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            summary = await client.store_backtest_run_summary(payload)
        finally:
            await client.aclose()

        self.assertEqual(summary["run_id"], "run-async-123")
        self.assertEqual(summary["start_ms"], 1714521600000)

    async def test_async_list_backtest_run_summaries_passes_filters(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(
                dict(request.url.params),
                {
                    "symbol": "EURUSD",
                    "timeframe": "M1",
                    "strategy_id": "ema-cross",
                    "engine": "vectorized",
                },
            )
            return httpx.Response(
                200,
                json=[
                    {
                        **payload,
                        "run_id": "run-async-123",
                        "persisted_at": "2026-05-15T12:34:56Z",
                    }
                ],
            )

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            summaries = await client.list_backtest_run_summaries(
                symbol="EURUSD",
                timeframe="M1",
                strategy_id="ema-cross",
                engine="vectorized",
            )
        finally:
            await client.aclose()

        self.assertEqual(summaries[0]["run_id"], "run-async-123")
        self.assertEqual(summaries[0]["end_ms"], 1714608000000)

    async def test_async_get_backtest_run_summary_uses_run_id(self) -> None:
        payload = _backtest_summary_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests/run-async-123")
            return httpx.Response(
                200,
                json={
                    **payload,
                    "run_id": "run-async-123",
                    "persisted_at": "2026-05-15T12:34:56Z",
                },
            )

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            summary = await client.get_backtest_run_summary("run-async-123")
        finally:
            await client.aclose()

        self.assertEqual(summary["run_id"], "run-async-123")
        self.assertEqual(summary["start_ms"], 1714521600000)

    async def test_async_backtest_run_summary_methods_raise_client_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests/run-missing")
            return httpx.Response(500, text="boom")

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                await client.get_backtest_run_summary("run-missing")
        finally:
            await client.aclose()

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.response_text, "boom")

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
