from __future__ import annotations

import unittest

from app.api.routers import market_data
from app.domain.value_objects import AccountId, Timeframe
from fastapi import HTTPException

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


if __name__ == "__main__":
    unittest.main()
