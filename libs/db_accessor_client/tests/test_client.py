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


def _backtest_run_payload(*, run_id: str = "run-123") -> dict:
    return {
        "run_id": run_id,
        "status": "queued",
        "submitted_at": "2026-06-08T12:30:00Z",
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "request_schema_version": 1,
        "request": {
            "symbols": ["EURUSD"],
            "exchange": "FX",
            "timeframe": "M15",
            "start_ms": 1714521600000,
            "end_ms": 1714608000000,
            "engine": "event_driven",
            "data_granularity": "bar",
            "initial_capital": 25000.0,
            "strategy": {
                "strategy_id": "sma_crossover",
                "parameters": {
                    "fast_window": 5,
                    "slow_window": 20,
                    "quantity": 1000.0,
                },
            },
            "execution": {
                "signal_timing": "close",
                "fill_timing": "next_open",
                "price_source": "open",
                "allow_partial_fills": False,
                "allow_short": False,
                "trade_accounting_policy": "average_cost",
                "gap_policy": "error",
                "intrabar_exit_policy": "take_profit_first",
                "commission_bps": 1.5,
                "slippage_bps": 0.75,
            },
            "persist_result": False,
            "run_metadata": {"label": "queued-smoke"},
        },
        "result_schema_version": None,
        "metrics": None,
        "diagnostics": None,
        "fills": [],
        "trades": [],
    }


def _completion_payload() -> dict:
    return {
        "expected_status": "running",
        "completed_at": "2026-06-08T12:35:00Z",
        "result_schema_version": 1,
        "metrics": {"total_return_pct": 1.25},
        "diagnostics": {"execution_duration_ms": 240000},
        "fills": [
            {
                "fill_sequence": 0,
                "timestamp_ms": 1714525200000,
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 1000.0,
                "price": 1.0715,
                "fees": 0.15,
                "exit_reason": None,
            }
        ],
        "trades": [
            {
                "trade_sequence": 0,
                "trade_id": "trade-1",
                "symbol": "EURUSD",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714525200000,
                "entry_price": 1.0715,
                "exit_timestamp_ms": 1714532400000,
                "exit_price": 1.074,
                "realized_pnl": 2.5,
                "fees": 0.3,
                "exit_reason": "take_profit",
            }
        ],
    }


def _fill_payload() -> dict:
    return {
        "run_id": "run-123",
        "fill_sequence": 0,
        "timestamp_ms": 1714525200000,
        "symbol": "EURUSD",
        "side": "buy",
        "quantity": 1000.0,
        "price": 1.0715,
        "fees": 0.15,
        "exit_reason": None,
    }


def _trade_payload() -> dict:
    return {
        "run_id": "run-123",
        "trade_sequence": 0,
        "trade_id": "trade-1",
        "symbol": "EURUSD",
        "quantity": 1000.0,
        "entry_timestamp_ms": 1714525200000,
        "entry_price": 1.0715,
        "exit_timestamp_ms": 1714532400000,
        "exit_price": 1.074,
        "realized_pnl": 2.5,
        "fees": 0.3,
        "exit_reason": "take_profit",
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

    def test_create_backtest_run_posts_versioned_payload(self) -> None:
        payload = _backtest_run_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(json.loads(request.content.decode()), payload)
            response_payload = {
                key: value for key, value in payload.items() if key not in {"fills", "trades"}
            }
            return httpx.Response(201, json=response_payload)

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            run = client.create_backtest_run(payload)
        finally:
            client.close()

        self.assertEqual(run["run_id"], "run-123")
        self.assertEqual(run["request"]["exchange"], "FX")
        self.assertEqual(
            run["request"]["strategy"]["parameters"]["fast_window"],
            5,
        )

    def test_get_backtest_run_uses_run_id(self) -> None:
        payload = _backtest_run_payload()
        response_payload = {
            key: value for key, value in payload.items() if key not in {"fills", "trades"}
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests/run-123")
            return httpx.Response(200, json=response_payload)

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            run = client.get_backtest_run("run-123")
        finally:
            client.close()

        self.assertEqual(run, response_payload)

    def test_list_backtest_runs_passes_all_filters_without_pagination(self) -> None:
        payload = _backtest_run_payload()
        response_payload = {
            key: value for key, value in payload.items() if key not in {"fills", "trades"}
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(request.url.params.get("status"), "queued")
            self.assertEqual(request.url.params.get("symbol"), "EURUSD")
            self.assertEqual(request.url.params.get("timeframe"), "M15")
            self.assertEqual(request.url.params.get("strategy"), "sma_crossover")
            self.assertEqual(request.url.params.get("engine"), "event_driven")
            self.assertEqual(
                request.url.params.get("submitted_from"),
                "2026-06-08T12:00:00+00:00",
            )
            self.assertEqual(
                request.url.params.get("submitted_to"),
                "2026-06-08T13:00:00+00:00",
            )
            self.assertNotIn("limit", request.url.params)
            self.assertNotIn("offset", request.url.params)
            return httpx.Response(200, json=[response_payload])

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            runs = client.list_backtest_runs(
                status="queued",
                symbol="EURUSD",
                timeframe="M15",
                strategy="sma_crossover",
                engine="event_driven",
                submitted_from="2026-06-08T12:00:00+00:00",
                submitted_to="2026-06-08T13:00:00+00:00",
            )
        finally:
            client.close()

        self.assertEqual(runs, [response_payload])

    def test_conditional_update_backtest_run_patches_expected_status(self) -> None:
        payload = {
            "expected_status": "queued",
            "new_status": "running",
            "started_at": "2026-06-08T12:31:00Z",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "PATCH")
            self.assertEqual(request.url.path, "/backtests/run-123")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(200, json={"updated": True})

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            updated = client.conditional_update_backtest_run("run-123", payload)
        finally:
            client.close()

        self.assertTrue(updated)

    def test_complete_backtest_run_posts_atomic_artifacts(self) -> None:
        payload = _completion_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests/run-123/complete")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(200, json={"updated": True})

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            updated = client.complete_backtest_run("run-123", payload)
        finally:
            client.close()

        self.assertTrue(updated)

    def test_get_execution_logs_and_delete_backtest_run(self) -> None:
        fill = _fill_payload()
        trade = _trade_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/backtests/run-123/fills":
                self.assertEqual(request.method, "GET")
                return httpx.Response(200, json=[fill])
            if request.url.path == "/backtests/run-123/trades":
                self.assertEqual(request.method, "GET")
                return httpx.Response(200, json=[trade])
            if request.url.path == "/backtests/run-123":
                self.assertEqual(request.method, "DELETE")
                return httpx.Response(204)
            return httpx.Response(404, text="missing")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            fills = client.get_backtest_fills("run-123")
            trades = client.get_backtest_trades("run-123")
            client.delete_backtest_run("run-123")
        finally:
            client.close()

        self.assertEqual(fills, [fill])
        self.assertEqual(trades, [trade])

    def test_delete_backtest_run_translates_http_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "DELETE")
            self.assertEqual(request.url.path, "/backtests/run-missing")
            return httpx.Response(404, text="missing")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                client.delete_backtest_run("run-missing")
        finally:
            client.close()

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.response_text, "missing")

    def test_backtest_run_methods_raise_client_error_on_http_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests/run-missing")
            return httpx.Response(404, text="missing")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                client.get_backtest_run("run-missing")
        finally:
            client.close()

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.response_text, "missing")

    def test_list_backtest_runs_raises_client_error_on_http_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests")
            return httpx.Response(503, text="unavailable")

        client = DatabaseAccessorClient()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                client.list_backtest_runs(status="queued")
        finally:
            client.close()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.response_text, "unavailable")

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

    async def test_async_create_backtest_run_posts_versioned_payload(self) -> None:
        payload = _backtest_run_payload(run_id="run-async-123")

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(json.loads(request.content.decode()), payload)
            response_payload = {
                key: value for key, value in payload.items() if key not in {"fills", "trades"}
            }
            return httpx.Response(201, json=response_payload)

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            run = await client.create_backtest_run(payload)
        finally:
            await client.aclose()

        self.assertEqual(run["run_id"], "run-async-123")
        self.assertEqual(run["request"]["exchange"], "FX")

    async def test_async_get_backtest_run_uses_run_id(self) -> None:
        payload = _backtest_run_payload(run_id="run-async-123")
        response_payload = {
            key: value for key, value in payload.items() if key not in {"fills", "trades"}
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests/run-async-123")
            return httpx.Response(200, json=response_payload)

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            run = await client.get_backtest_run("run-async-123")
        finally:
            await client.aclose()

        self.assertEqual(run, response_payload)

    async def test_async_list_backtest_runs_passes_all_filters(self) -> None:
        payload = _backtest_run_payload(run_id="run-async-123")
        response_payload = {
            key: value for key, value in payload.items() if key not in {"fills", "trades"}
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/backtests")
            self.assertEqual(
                dict(request.url.params),
                {
                    "status": "running",
                    "symbol": "EURUSD",
                    "timeframe": "M15",
                    "strategy": "sma_crossover",
                    "engine": "event_driven",
                    "submitted_from": "2026-06-08T12:00:00+00:00",
                    "submitted_to": "2026-06-08T13:00:00+00:00",
                },
            )
            return httpx.Response(200, json=[response_payload])

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            runs = await client.list_backtest_runs(
                status="running",
                symbol="EURUSD",
                timeframe="M15",
                strategy="sma_crossover",
                engine="event_driven",
                submitted_from="2026-06-08T12:00:00+00:00",
                submitted_to="2026-06-08T13:00:00+00:00",
            )
        finally:
            await client.aclose()

        self.assertEqual(runs, [response_payload])

    async def test_async_conditional_update_backtest_run_patches_expected_status(
        self,
    ) -> None:
        payload = {
            "expected_status": "queued",
            "new_status": "running",
            "started_at": "2026-06-08T12:31:00Z",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "PATCH")
            self.assertEqual(request.url.path, "/backtests/run-async-123")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(200, json={"updated": True})

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            updated = await client.conditional_update_backtest_run(
                "run-async-123",
                payload,
            )
        finally:
            await client.aclose()

        self.assertTrue(updated)

    async def test_async_complete_backtest_run_posts_atomic_artifacts(self) -> None:
        payload = _completion_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/backtests/run-async-123/complete")
            self.assertEqual(json.loads(request.content.decode()), payload)
            return httpx.Response(200, json={"updated": True})

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            updated = await client.complete_backtest_run(
                "run-async-123",
                payload,
            )
        finally:
            await client.aclose()

        self.assertTrue(updated)

    async def test_async_get_execution_logs_and_delete_backtest_run(self) -> None:
        fill = {**_fill_payload(), "run_id": "run-async-123"}
        trade = {**_trade_payload(), "run_id": "run-async-123"}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/backtests/run-async-123/fills":
                self.assertEqual(request.method, "GET")
                return httpx.Response(200, json=[fill])
            if request.url.path == "/backtests/run-async-123/trades":
                self.assertEqual(request.method, "GET")
                return httpx.Response(200, json=[trade])
            if request.url.path == "/backtests/run-async-123":
                self.assertEqual(request.method, "DELETE")
                return httpx.Response(204)
            return httpx.Response(404, text="missing")

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            fills = await client.get_backtest_fills("run-async-123")
            trades = await client.get_backtest_trades("run-async-123")
            await client.delete_backtest_run("run-async-123")
        finally:
            await client.aclose()

        self.assertEqual(fills, [fill])
        self.assertEqual(trades, [trade])

    async def test_async_backtest_run_methods_raise_client_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests/run-missing")
            return httpx.Response(500, text="boom")

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                await client.get_backtest_run("run-missing")
        finally:
            await client.aclose()

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.response_text, "boom")

    async def test_async_list_backtest_runs_raises_client_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/backtests")
            return httpx.Response(503, text="unavailable")

        client = AsyncDatabaseAccessorClient()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(DatabaseAccessorClientError) as ctx:
                await client.list_backtest_runs(status="running")
        finally:
            await client.aclose()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.response_text, "unavailable")

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
