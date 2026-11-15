from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable, Callable

from app.domain.models import Trendbar
from app.domain.value_objects import AccountId, Timeframe
from app.infrastructure.stream_registry import TrendbarSubscription
from app.infrastructure.trendbar_stream_registry import TrendbarStreamRegistry
from app.settings import Settings


class TrendbarStreamRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_every_live_update(self) -> None:
        published: list[Trendbar] = []
        handler: Callable[[Trendbar], Awaitable[None]] | None = None

        async def subscribe_fn(account_id, symbol, timeframe, callback, expected_symbol_id=None):
            nonlocal handler
            handler = callback
            return TrendbarSubscription(
                account_id=account_id,
                symbol=symbol,
                symbol_id=1,
                timeframe=timeframe,
                token="token",
            )

        async def unsubscribe_fn(_subscription):
            return None

        async def publisher(_account_id, _symbol, _timeframe, bar):
            published.append(bar)

        registry = TrendbarStreamRegistry(
            subscribe_fn=subscribe_fn,
            unsubscribe_fn=unsubscribe_fn,
            publisher=publisher,
            settings=Settings(),
        )

        await registry.start_trendbar_stream(AccountId(1), "EURUSD", Timeframe.M1)
        assert handler is not None

        await handler(
            Trendbar(
                o=Decimal("1.10"),
                h=Decimal("1.20"),
                l=Decimal("1.00"),
                c=Decimal("1.15"),
                v=10,
                t=1000,
            )
        )
        await handler(
            Trendbar(
                o=Decimal("1.10"),
                h=Decimal("1.25"),
                l=Decimal("0.95"),
                c=Decimal("1.18"),
                v=12,
                t=1000,
            )
        )
        await handler(
            Trendbar(
                o=Decimal("1.18"),
                h=Decimal("1.30"),
                l=Decimal("1.10"),
                c=Decimal("1.26"),
                v=11,
                t=1060,
            )
        )

        await asyncio.wait_for(self._wait_for_publish_count(published, 3), timeout=1.0)
        self.assertEqual([bar.t for bar in published], [1000, 1000, 1060])

        await registry.stop_trendbar_stream(AccountId(1), "EURUSD", Timeframe.M1)

    async def _wait_for_publish_count(self, published: list[Trendbar], expected: int) -> None:
        while len(published) < expected:
            await asyncio.sleep(0.01)


if __name__ == "__main__":
    unittest.main()


class BoundTrendbarStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_mismatched_start_or_stop_preserves_original_subscription(self) -> None:
        from unittest.mock import AsyncMock

        from app.domain.instrument_binding import BrokerInstrumentMismatchError

        subscription = TrendbarSubscription(123, "EURUSD", 1, Timeframe.M1, "token")
        subscribe = AsyncMock(return_value=subscription)
        unsubscribe = AsyncMock()
        registry = TrendbarStreamRegistry(subscribe, unsubscribe, AsyncMock(), Settings())
        try:
            await registry.start_trendbar_stream(
                AccountId(123), "EURUSD", Timeframe.M1, expected_symbol_id=1
            )
            self.assertEqual(subscribe.call_args.args[-1], 1)
            with self.assertRaises(BrokerInstrumentMismatchError):
                await registry.start_trendbar_stream(
                    AccountId(123), "EURUSD", Timeframe.M1, expected_symbol_id=2
                )
            with self.assertRaises(BrokerInstrumentMismatchError):
                await registry.stop_trendbar_stream(
                    AccountId(123), "EURUSD", Timeframe.M1, expected_symbol_id=2
                )
            self.assertEqual(registry.active_stream_count(), 1)
            unsubscribe.assert_not_awaited()
            await registry.stop_trendbar_stream(
                AccountId(123), "EURUSD", Timeframe.M1, expected_symbol_id=1
            )
            unsubscribe.assert_awaited_once_with(subscription)
            subscribe.assert_awaited_once()
        finally:
            await registry.shutdown()
