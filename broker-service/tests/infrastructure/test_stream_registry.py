from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from app.domain.instrument_binding import BrokerInstrumentMismatchError
from app.domain.value_objects import AccountId, TickStreamOptions
from app.infrastructure.stream_registry import StreamRegistry, TickSubscription
from app.settings import Settings


class BoundTickStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_handle_controls_cleanup_after_source_remap(self) -> None:
        subscription = TickSubscription(123, "EURUSD", 1, "token")
        subscribe = AsyncMock(return_value=subscription)
        unsubscribe = AsyncMock()
        registry = StreamRegistry(subscribe, unsubscribe, AsyncMock(), Settings())
        try:
            await registry.start_tick_stream(
                AccountId(123), "EURUSD", TickStreamOptions(), expected_symbol_id=1
            )
            self.assertEqual(subscribe.call_args.args[-1], 1)
            with self.assertRaises(BrokerInstrumentMismatchError):
                await registry.start_tick_stream(
                    AccountId(123), "EURUSD", TickStreamOptions(), expected_symbol_id=2
                )
            with self.assertRaises(BrokerInstrumentMismatchError):
                await registry.stop_tick_stream(AccountId(123), "EURUSD", expected_symbol_id=2)
            self.assertEqual(registry.active_stream_count(), 1)
            unsubscribe.assert_not_awaited()
            await registry.stop_tick_stream(AccountId(123), "EURUSD", expected_symbol_id=1)
            unsubscribe.assert_awaited_once_with(subscription)
        finally:
            await registry.shutdown()
