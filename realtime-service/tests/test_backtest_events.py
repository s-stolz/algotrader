import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

from app.backtest_events import BacktestEventBridge


class BacktestBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscription_fanout_and_upstream_reconnection_refresh_signal(self):
        incoming = asyncio.Queue()

        async def read(*args, **kwargs):
            value = await incoming.get()
            if isinstance(value, Exception):
                raise value
            return value

        redis = Mock(
            xrevrange=AsyncMock(return_value=[]),
            xread=AsyncMock(side_effect=read),
            aclose=AsyncMock(),
        )
        bridge = BacktestEventBridge(redis)
        client = Mock(send=AsyncMock(), close=AsyncMock())
        await bridge.subscribe(client)
        bridge.start()

        async def wait_for(predicate):
            async with asyncio.timeout(3):
                while not predicate():
                    await asyncio.sleep(0.01)

        def messages():
            return [json.loads(call.args[0]) for call in client.send.call_args_list]

        try:
            await wait_for(lambda: bridge._connected)
            await incoming.put([("stream", [("1-0", {"payload": '{"type":"backtestChanged"}'})])])
            await wait_for(lambda: {"type": "backtestChanged"} in messages())
            with self.assertLogs("app.backtest_events"):
                await incoming.put(ConnectionError("lost upstream"))
                await wait_for(lambda: not bridge._connected)
            await wait_for(
                lambda: sum(message["type"] == "backtestConnection" for message in messages()) == 4
            )
            statuses = [
                message["connected"]
                for message in messages()
                if message["type"] == "backtestConnection"
            ]
            self.assertEqual(statuses, [False, True, False, True])
            bridge.unsubscribe(client)
            count = client.send.call_count
            await bridge._broadcast({"type": "backtestChanged"})
            self.assertEqual(client.send.call_count, count)
        finally:
            await bridge.close()
        redis.aclose.assert_awaited_once()

    async def test_failed_browser_is_removed_without_interrupting_other_subscribers(self):
        bridge = BacktestEventBridge(Mock())
        failed = Mock(send=AsyncMock(side_effect=ConnectionError()), close=AsyncMock())
        healthy = Mock(send=AsyncMock(), close=AsyncMock())
        bridge._clients.update({failed, healthy})
        await bridge._broadcast({"type": "backtestChanged"})
        healthy.send.assert_awaited_once()
        self.assertNotIn(failed, bridge._clients)
