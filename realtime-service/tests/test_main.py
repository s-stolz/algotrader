import json
import unittest
from unittest.mock import AsyncMock, Mock

from main import WebSocketServer


class MarketMessageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = WebSocketServer({})
        self.manager = Mock(
            subscribe_candles=AsyncMock(),
            unsubscribe_candles=AsyncMock(),
            subscribe_indicator=AsyncMock(return_value={"stream_id": "stream"}),
            unsubscribe_indicator=AsyncMock(),
        )
        self.server.subscription_manager = self.manager
        self.socket = Mock(send=AsyncMock())

    async def test_market_id_required_for_all_live_commands(self):
        for command in (
            "subscribeCandles",
            "unsubscribeCandles",
            "subscribeIndicator",
            "unsubscribeIndicator",
        ):
            for market_id in (None, "1", True, 0, -1):
                with (
                    self.subTest(command=command, market_id=market_id),
                    self.assertRaises(ValueError),
                ):
                    await self.server.handle_message(
                        self.socket,
                        1,
                        json.dumps(
                            {
                                "type": command,
                                "market_id": market_id,
                                "symbol": "EURUSD",
                                "timeframe": "M1",
                                "indicatorId": 1,
                                "clientIndicatorId": "sma",
                            }
                        ),
                    )
        self.manager.subscribe_candles.assert_not_awaited()
        self.manager.subscribe_indicator.assert_not_awaited()

    async def test_market_id_is_authority_instead_of_supplied_symbol(self):
        await self.server.handle_message(
            self.socket,
            1,
            json.dumps(
                {
                    "type": "subscribeCandles",
                    "market_id": 7,
                    "symbol": "wrong",
                    "timeframe": "M1",
                }
            ),
        )
        self.manager.subscribe_candles.assert_awaited_once_with(1, 7, "M1")
        self.assertEqual(
            json.loads(self.socket.send.call_args.args[0]),
            {
                "type": "subscribed",
                "market_id": 7,
                "timeframe": "M1",
            },
        )

    async def test_history_subscription_validates_source_before_registering(self):
        self.manager.market_resolver = Mock(
            resolve=AsyncMock(side_effect=ValueError("Custom market"))
        )
        bridge = Mock(subscribe=AsyncMock())
        self.server.history_download_events = bridge
        with self.assertRaisesRegex(ValueError, "Custom"):
            await self.server.handle_message(
                self.socket,
                1,
                json.dumps(
                    {
                        "type": "subscribeHistoryDownloads",
                        "market_id": 7,
                    }
                ),
            )
        bridge.subscribe.assert_not_awaited()

    async def test_history_unsubscribe_does_not_require_deleted_market_lookup(self):
        self.manager.market_resolver = Mock(resolve=AsyncMock())
        bridge = Mock(unsubscribe=Mock())
        self.server.history_download_events = bridge
        await self.server.handle_message(
            self.socket,
            1,
            json.dumps(
                {
                    "type": "unsubscribeHistoryDownloads",
                    "market_id": 7,
                }
            ),
        )
        bridge.unsubscribe.assert_called_once_with(self.socket, 7)
        self.manager.market_resolver.resolve.assert_not_awaited()
