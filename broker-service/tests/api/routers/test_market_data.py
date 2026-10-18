from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
from app.api.dependencies import get_account_id, get_market_data_service
from app.api.routers import market_data
from app.domain.models import Symbol, Trendbar
from app.domain.value_objects import AccountId, SymbolDescriptor, SymbolId, Timeframe
from app.infrastructure.ctrader_client import CtraderClient
from app.settings import CtraderCredentials
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetTrendbarsRes
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbar
from fastapi import FastAPI, HTTPException

from .fakes import FakeMarketDataService


class MarketDataRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_symbols_camel_case(self) -> None:
        response = await market_data.list_symbols(AccountId(123), FakeMarketDataService())
        self.assertIn("symbolId", response[0])
        self.assertIn("symbolName", response[0])

    async def test_get_symbol_shape(self) -> None:
        response = await market_data.get_symbol("EURUSD", AccountId(123), FakeMarketDataService())
        self.assertIn("symbol_id", response)

    async def test_get_trendbars_excludes_digits(self) -> None:
        response = await market_data.get_trendbars(
            symbol="EURUSD",
            timeframe=Timeframe.M1,
            from_ts=None,
            to_ts=None,
            limit=1,
            account_id=AccountId(123),
            service=FakeMarketDataService(),
        )
        self.assertNotIn("digits", response[0])

    async def test_get_trendbars_requires_from_or_limit(self) -> None:
        with self.assertRaises(HTTPException):
            await market_data.get_trendbars(
                symbol="EURUSD",
                timeframe=Timeframe.M1,
                from_ts=None,
                to_ts=None,
                limit=None,
                account_id=AccountId(123),
                service=FakeMarketDataService(),
            )

    async def test_start_trendbar_stream_without_only_completed_bars(self) -> None:
        response = await market_data.start_trendbar_stream(
            symbol="EURUSD",
            timeframe=Timeframe.M1,
            account_id=AccountId(123),
            service=FakeMarketDataService(),
        )
        self.assertTrue(response["running"])


# Load the real ingestion consumer without colliding with the broker's `app` package.
INGESTION = Path(__file__).resolve().parents[4] / "ingestion-service"
spec = importlib.util.spec_from_file_location("app.utils", INGESTION / "app/utils.py")
assert spec and spec.loader
utils = importlib.util.module_from_spec(spec)
sys.modules["app.utils"] = utils
spec.loader.exec_module(utils)
spec = importlib.util.spec_from_file_location(
    "history_consumer", INGESTION / "app/broker_client.py"
)
assert spec and spec.loader
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def provider_history(timestamps, page_limit=1, fail_after=None):
    client = CtraderClient(
        CtraderCredentials(
            client_id="test",
            secret="test",
            host_type="demo",
            access_token="test",
            refresh_token="test",
            token_url="http://unused",
            access_token_expires_in_seconds=3600,
            token_request_timeout_seconds=1,
        )
    )
    client._symbol_cache.store_descriptor(SymbolDescriptor(SymbolId(1), "EURUSD", True))
    client._symbol_cache.store_full_symbol(Symbol(1, "EURUSD", 5, 4))
    calls = []

    async def send(request):
        calls.append((request.fromTimestamp, request.toTimestamp))
        if fail_after is not None and len(calls) > fail_after:
            raise RuntimeError("interrupted provider")
        selected = [t for t in timestamps if request.fromTimestamp <= t <= request.toTimestamp]
        return ProtoOAGetTrendbarsRes(
            ctidTraderAccountId=123,
            period=request.period,
            timestamp=request.toTimestamp,
            trendbar=[
                ProtoOATrendbar(
                    utcTimestampInMinutes=t // 60000,
                    low=100000,
                    deltaOpen=0,
                    deltaHigh=1,
                    deltaClose=1,
                    volume=1,
                )
                for t in selected[-min(page_limit, request.count) :]
            ],
        )

    client._send_request = AsyncMock(side_effect=send)
    return client, calls


class HistoryContractTests(unittest.IsolatedAsyncioTestCase):
    async def consume(self, service, start=60000, end=180000):
        app = FastAPI()
        app.include_router(market_data.router)
        app.dependency_overrides[get_account_id] = lambda: AccountId(123)
        app.dependency_overrides[get_market_data_service] = lambda: service
        client = consumer.BrokerClient("http://broker", "123")
        await client.async_client.aclose()
        client.async_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
        try:
            return [
                bar
                async for bar in client.stream_trendbars("EURUSD", start_time=start, end_time=end)
            ]
        finally:
            client.close()
            await client.aclose()

    async def test_upstream_failure_is_not_successful_empty_history(self):
        class FailedHistory:
            async def stream_trendbars(self, *args):
                if False:
                    yield
                raise RuntimeError("provider unavailable")

        with self.assertRaises(RuntimeError):
            await self.consume(FailedHistory())

    async def test_completed_empty_interval_is_valid(self):
        class EmptyHistory:
            async def stream_trendbars(self, *args):
                if False:
                    yield

        self.assertEqual(await self.consume(EmptyHistory()), [])

    async def test_eof_without_completion_is_failure(self):
        client = consumer.BrokerClient("http://broker", "123")
        await client.async_client.aclose()
        client.async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    text=json.dumps({"o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "t": 60000}) + "\n",
                )
            )
        )
        try:
            with self.assertRaises(RuntimeError):
                _ = [
                    bar
                    async for bar in client.stream_trendbars(
                        "EURUSD", start_time=60000, end_time=180000
                    )
                ]
        finally:
            client.close()
            await client.aclose()

    async def test_provider_short_pages_exhaust_final_chunk(self):
        provider, _ = provider_history([60000, 120000, 180000])
        bars = await self.consume(provider)
        self.assertEqual([bar["t"] for bar in bars], [60000, 120000, 180000])

    async def test_provider_failure_after_first_page_reaches_ingestion(self):
        provider, _ = provider_history([60000, 120000, 180000], fail_after=1)
        with self.assertRaises(RuntimeError):
            await self.consume(provider)

    async def test_provider_empty_early_window_does_not_hide_later_history(self):
        provider, _ = provider_history([600060000])
        bars = await self.consume(provider, start=60000, end=600120000)
        self.assertEqual([bar["t"] for bar in bars], [600060000])

    async def test_error_after_delivered_candle_is_failure(self):
        class InterruptedHistory:
            async def stream_trendbars(self, *args):
                yield Trendbar(Decimal(1), Decimal(1), Decimal(1), Decimal(1), 1, 60000)
                raise ValueError("provider response interrupted")

        with self.assertRaises(RuntimeError):
            await self.consume(InterruptedHistory())

    async def test_completion_count_and_interval_must_match(self):
        for completion in (
            {
                "type": "complete",
                "version": 1,
                "count": 1,
                "fromTs": 60000,
                "toTs": 180000,
                "limit": None,
            },
            {
                "type": "complete",
                "version": 1,
                "count": 0,
                "fromTs": 60001,
                "toTs": 180000,
                "limit": None,
            },
        ):
            with self.subTest(completion=completion):
                client = consumer.BrokerClient("http://broker", "123")
                await client.async_client.aclose()
                client.async_client = httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, text=json.dumps(completion) + "\n")
                    )
                )
                try:
                    with self.assertRaises(RuntimeError):
                        _ = [
                            bar
                            async for bar in client.stream_trendbars(
                                "EURUSD", start_time=60000, end_time=180000
                            )
                        ]
                finally:
                    client.close()
                    await client.aclose()

    async def test_limited_history_keeps_newest_candles_despite_provider_cap(self):
        provider, _ = provider_history([60000, 120000, 180000])
        bars = await provider.get_trendbars(
            AccountId(123), "EURUSD", Timeframe.M1, 60000, 180000, 2
        )
        self.assertEqual([bar.t for bar in bars], [120000, 180000])


if __name__ == "__main__":
    unittest.main()
