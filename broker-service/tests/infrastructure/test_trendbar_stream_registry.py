from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal

from app.domain.models import Trendbar
from app.domain.value_objects import AccountId, Timeframe
from app.infrastructure.stream_registry import TrendbarSubscription
from app.infrastructure.trendbar_stream_registry import TrendbarStreamRegistry
from app.settings import Settings


class TrendbarStreamRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_every_live_update(self) -> None:
        published: list[Trendbar] = []
        handler = None

        async def subscribe_fn(account_id, symbol, timeframe, callback):
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
