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
            get=AsyncMock(return_value=None),
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
            progress = {"type": "backtestProgress", "run_id": "run-a", "stage": "saving"}
            await incoming.put([("stream", [("2-0", {"payload": json.dumps(progress)})])])
            await wait_for(lambda: progress in messages())
            redis.get.return_value = json.dumps(progress)
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

    async def test_subscriber_joining_recovery_fanout_restores_latest_progress(self):
        progress = {"type": "backtestProgress", "run_id": "run-a", "stage": "simulating"}
        snapshot_started = asyncio.Event()
        release_snapshot = asyncio.Event()
        reading_started = asyncio.Event()

        async def send(payload):
            if json.loads(payload) == progress:
                snapshot_started.set()
                await release_snapshot.wait()

        async def read(*args, **kwargs):
            reading_started.set()
            await asyncio.Future()

        redis = Mock(
            xrevrange=AsyncMock(return_value=[("10-0", {"payload": json.dumps(progress)})]),
            get=AsyncMock(return_value=json.dumps(progress)),
            xread=AsyncMock(side_effect=read),
            aclose=AsyncMock(),
        )
        bridge = BacktestEventBridge(redis)
        existing = Mock(send=AsyncMock(side_effect=send), close=AsyncMock())
        await bridge.subscribe(existing)
        bridge.start()
        try:
            await asyncio.wait_for(snapshot_started.wait(), timeout=3)
            joining = Mock(send=AsyncMock(), close=AsyncMock())
            await bridge.subscribe(joining)
            release_snapshot.set()
            await asyncio.wait_for(reading_started.wait(), timeout=3)
            messages = [json.loads(call.args[0]) for call in joining.send.call_args_list]
            self.assertIn(progress, messages)
            self.assertIn({"type": "backtestConnection", "connected": True}, messages)
            redis.xread.assert_awaited_once_with(
                {"backtests:events:v1": "10-0"}, block=1000, count=100
            )
        finally:
            release_snapshot.set()
            await bridge.close()

    async def test_subscriber_restores_latest_progress_without_lifecycle_refresh(self):
        progress = {"type": "backtestProgress", "run_id": "run-a", "stage": "simulating"}
        redis = Mock(get=AsyncMock(return_value=json.dumps(progress)))
        bridge = BacktestEventBridge(redis)
        bridge._connected = True
        client = Mock(send=AsyncMock(), close=AsyncMock())
        await bridge.subscribe(client)
        messages = [json.loads(call.args[0]) for call in client.send.call_args_list]
        self.assertEqual(messages, [progress, {"type": "backtestConnection", "connected": True}])
        redis.get.assert_awaited_once_with("backtests:progress:v1")

    async def test_failed_browser_is_removed_without_interrupting_other_subscribers(self):
        bridge = BacktestEventBridge(Mock())
        failed = Mock(send=AsyncMock(side_effect=ConnectionError()), close=AsyncMock())
        healthy = Mock(send=AsyncMock(), close=AsyncMock())
        bridge._clients.update({failed, healthy})
        await bridge._broadcast({"type": "backtestChanged"})
        healthy.send.assert_awaited_once()
        self.assertNotIn(failed, bridge._clients)
