import unittest
from unittest.mock import AsyncMock, Mock

from app.subscription_manager import SubscriptionManager

ASSETS = ["EURUSD", "USDJPY", "USDCHF", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD"]


class IndicatorSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.broker = Mock(start_trendbar_stream=AsyncMock(), stop_trendbar_stream=AsyncMock())
        self.consumer = Mock(start_indicator_stream=AsyncMock(), start_candle_stream=AsyncMock())
        self.api = Mock(
            get_indicator_metadata=AsyncMock(
                return_value={"inputs": ASSETS, "supports_live": True}
            ),
            start_live_indicator_stream=AsyncMock(
                return_value={"stream_id": "fx", "redis_stream_key": "indicators:fx"}
            ),
            stop_live_indicator_stream=AsyncMock(),
        )
        self.resolver = Mock(
            resolve=AsyncMock(
                return_value={"symbol_id": 1, "symbol": "EURUSD", "exchange": "BROKER"}
            ),
            dependencies=AsyncMock(
                side_effect=lambda market, symbols: [
                    {"symbol": symbol} for symbol in symbols or [market["symbol"]]
                ]
            ),
        )
        self.manager = SubscriptionManager(self.broker, self.consumer, self.api, self.resolver)
        self.first = self.manager.register_client(Mock())
        self.second = self.manager.register_client(Mock())

    async def subscribe(self, client):
        return await self.manager.subscribe_indicator(
            client_id=client,
            market_id=1,
            timeframe="M1",
            indicator_id=5,
            parameters={},
            client_indicator_id="strength",
        )

    async def test_basket_sources_shared_with_chart_and_clients_and_released_on_disconnect(self):
        await self.manager.subscribe_candles(self.first, 1, "M1")
        await self.subscribe(self.first)
        await self.subscribe(self.first)
        await self.subscribe(self.second)
        self.assertEqual(self.broker.start_trendbar_stream.await_count, 7)
        self.assertEqual(self.api.start_live_indicator_stream.await_count, 1)
        self.assertEqual(self.manager.source_dependency_counts["source:EURUSD:M1"], 3)
        await self.manager.unregister_client(self.first)
        self.broker.stop_trendbar_stream.assert_not_awaited()
        await self.manager.unregister_client(self.second)
        self.assertEqual(self.broker.stop_trendbar_stream.await_count, 7)
        self.api.stop_live_indicator_stream.assert_awaited_once()
        self.assertFalse(self.manager.source_dependency_counts)
        self.assertFalse(self.manager.subscription_counts)

    async def test_partial_source_failure_rolls_back_only_acquired_dependencies(self):
        await self.manager.subscribe_candles(self.first, 1, "M1")
        self.broker.start_trendbar_stream.side_effect = [None, RuntimeError("source failed")]
        with self.assertRaisesRegex(RuntimeError, "source failed"):
            await self.subscribe(self.second)
        self.assertEqual(self.manager.source_dependency_counts, {"source:EURUSD:M1": 1})
        self.broker.stop_trendbar_stream.assert_awaited_once_with("USDJPY", "M1")
        self.api.start_live_indicator_stream.assert_not_awaited()
        self.assertFalse(self.manager.client_subscriptions[self.second])

    async def test_indicator_start_failure_releases_basket(self):
        self.api.start_live_indicator_stream.side_effect = RuntimeError("indicator failed")
        with self.assertRaisesRegex(RuntimeError, "indicator failed"):
            await self.subscribe(self.first)
        self.assertEqual(self.broker.stop_trendbar_stream.await_count, 7)
        self.assertFalse(self.manager.source_dependency_counts)
        self.assertFalse(self.manager.subscription_counts)

    async def test_fanout_failure_stops_indicator_and_releases_sources(self):
        self.consumer.start_indicator_stream.side_effect = RuntimeError("fanout failed")
        with self.assertRaisesRegex(RuntimeError, "fanout failed"):
            await self.subscribe(self.first)
        self.api.stop_live_indicator_stream.assert_awaited_once()
        self.assertFalse(self.manager.indicator_meta_by_sub_key)
        self.assertFalse(self.manager.indicator_sub_key_by_stream_id)
        self.assertFalse(self.manager.source_dependency_counts)

    async def test_ordinary_indicator_uses_chart_symbol(self):
        self.api.get_indicator_metadata.return_value = {"inputs": [], "supports_live": True}
        await self.subscribe(self.first)
        self.broker.start_trendbar_stream.assert_awaited_once_with("EURUSD", "M1")
        await self.manager.unregister_client(self.first)
        self.broker.stop_trendbar_stream.assert_awaited_once_with("EURUSD", "M1")

    async def test_concurrent_subscribers_share_one_basket_session(self):
        import asyncio

        entered = asyncio.Event()
        release = asyncio.Event()

        async def start(**kwargs):
            entered.set()
            await release.wait()
            return {"stream_id": "fx", "redis_stream_key": "indicators:fx"}

        self.api.start_live_indicator_stream.side_effect = start
        first = asyncio.create_task(self.subscribe(self.first))
        await entered.wait()
        second = asyncio.create_task(self.subscribe(self.second))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
        self.api.start_live_indicator_stream.assert_awaited_once()
        self.assertEqual(self.broker.start_trendbar_stream.await_count, 7)
        await asyncio.gather(
            self.manager.unregister_client(self.first), self.manager.unregister_client(self.second)
        )
        self.api.stop_live_indicator_stream.assert_awaited_once()
        self.assertFalse(self.manager.source_dependency_counts)

    async def test_replay_marker_reaches_browser_without_extra_control_messages(self):
        import asyncio
        import json

        ws = Mock(send=AsyncMock())
        self.manager.clients[self.first] = ws
        await self.subscribe(self.first)
        self.manager.broadcast_indicator(
            "fx", {"timestamp_ms": 60000, "values": {"EUR": 1.5}, "replay": True}
        )
        await asyncio.sleep(0)
        message = json.loads(ws.send.call_args.args[0])
        self.assertEqual(message["type"], "indicatorUpdate")
        self.assertTrue(message["replay"])
        self.assertEqual(message["values"], {"EUR": 1.5})

    async def test_custom_market_rejected_before_broker_or_indicator_dependencies(self):
        self.resolver.resolve.side_effect = ValueError("Custom markets do not support broker data")
        with self.assertRaisesRegex(ValueError, "Custom"):
            await self.manager.subscribe_candles(self.first, 1, "M1")
        with self.assertRaisesRegex(ValueError, "Custom"):
            await self.subscribe(self.first)
        self.broker.start_trendbar_stream.assert_not_awaited()
        self.api.start_live_indicator_stream.assert_not_awaited()
        self.assertFalse(self.manager.client_subscriptions[self.first])

    async def test_ineligible_basket_input_rejected_before_acquiring_any_sources(self):
        self.resolver.dependencies.side_effect = ValueError(
            "Live input requires one connected broker market"
        )
        with self.assertRaisesRegex(ValueError, "Live input"):
            await self.subscribe(self.first)
        self.broker.start_trendbar_stream.assert_not_awaited()
        self.api.start_live_indicator_stream.assert_not_awaited()

    async def test_candle_fanout_is_bound_to_market_id(self):
        import asyncio
        import json

        first = Mock(send=AsyncMock())
        second = Mock(send=AsyncMock())
        self.manager.clients[self.first] = first
        self.manager.clients[self.second] = second
        self.resolver.resolve.side_effect = [
            {"symbol_id": 1, "symbol": "EURUSD", "exchange": "BROKER"},
            ValueError("Custom markets do not support broker data"),
        ]
        await self.manager.subscribe_candles(self.first, 1, "M1")
        with self.assertRaises(ValueError):
            await self.manager.subscribe_candles(self.second, 2, "M1")
        self.manager.broadcast_candle("EURUSD", "M1", {"timestamp_ms": 60000, "close": 1.2})
        await asyncio.sleep(0)
        self.assertEqual(json.loads(first.send.call_args.args[0])["market_id"], 1)
        second.send.assert_not_awaited()

    async def test_concurrent_candle_subscriptions_share_source_and_release_once(self):
        import asyncio

        await asyncio.gather(
            self.manager.subscribe_candles(self.first, 1, "M1"),
            self.manager.subscribe_candles(self.second, 1, "M1"),
        )
        self.broker.start_trendbar_stream.assert_awaited_once_with("EURUSD", "M1")
        self.consumer.start_candle_stream.assert_awaited_once_with("EURUSD", "M1")
        await self.manager.unregister_client(self.first)
        self.consumer.stop_stream.assert_not_called()
        await self.manager.unregister_client(self.second)
        self.consumer.stop_stream.assert_called_once()
        self.broker.stop_trendbar_stream.assert_awaited_once_with("EURUSD", "M1")
