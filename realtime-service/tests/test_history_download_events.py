import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

from app.history_download_events import HistoryDownloadEventBridge


def changed(market_id=1, revision=2):
    return {
        "type": "historyDownloadChanged",
        "market_id": market_id,
        "job_id": "job",
        "revision": revision,
    }


def messages(client):
    return [json.loads(call.args[0]) for call in client.send.call_args_list]


class HistoryDownloadBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_notifications_only_reach_subscribed_markets(self):
        bridge = HistoryDownloadEventBridge(Mock())
        first = Mock(send=AsyncMock(), close=AsyncMock())
        second = Mock(send=AsyncMock(), close=AsyncMock())
        await bridge.subscribe(first, 1)
        await bridge.subscribe(first, 1)
        await bridge.subscribe(first, 2)
        await bridge.subscribe(second, 2)
        await bridge._broadcast(changed(1))
        self.assertEqual(messages(first).count(changed(1)), 1)
        self.assertNotIn(changed(1), messages(second))
        bridge.unsubscribe(first, 1)
        await bridge._broadcast(changed(1, 3))
        self.assertNotIn(changed(1, 3), messages(first))
        await bridge._broadcast(changed(2))
        self.assertIn(changed(2), messages(first))
        self.assertIn(changed(2), messages(second))
        bridge.unsubscribe(first)
        await bridge._broadcast(changed(2, 3))
        self.assertNotIn(changed(2, 3), messages(first))

    async def test_upstream_reconnect_signals_snapshot_refresh_with_concrete_cursor(self):
        incoming = asyncio.Queue()

        async def read(*args, **kwargs):
            item = await incoming.get()
            if isinstance(item, Exception):
                raise item
            return item

        redis = Mock(
            xrevrange=AsyncMock(return_value=[("10-0", {})]),
            xread=AsyncMock(side_effect=read),
            aclose=AsyncMock(),
        )
        bridge = HistoryDownloadEventBridge(redis)
        client = Mock(send=AsyncMock(), close=AsyncMock())
        await bridge.subscribe(client, 1)
        bridge.start()

        async def wait_for(predicate):
            async with asyncio.timeout(3):
                while not predicate():
                    await asyncio.sleep(0.01)

        try:
            await wait_for(lambda: redis.xread.await_count == 1)
            redis.xread.assert_awaited_with(
                {"history:downloads:events": "10-0"}, block=1000, count=100
            )
            await incoming.put(
                [
                    (
                        "stream",
                        [
                            ("11-0", {"event": "invalid"}),
                            ("12-0", {"event": json.dumps(changed())}),
                        ],
                    )
                ]
            )
            await wait_for(lambda: changed() in messages(client))
            with self.assertLogs("app.history_download_events"):
                await incoming.put(ConnectionError("disconnected"))
                await wait_for(lambda: not bridge._connected)
            # The connected flag changes before asynchronous client delivery completes.
            await wait_for(lambda: redis.xread.await_count == 3)
            redis.xrevrange.assert_awaited_with("history:downloads:events", count=1)
            redis.xread.assert_awaited_with(
                {"history:downloads:events": "10-0"}, block=1000, count=100
            )
            statuses = [
                message["connected"]
                for message in messages(client)
                if message["type"] == "historyDownloadsConnection"
            ]
            self.assertEqual(statuses, [False, True, False, True])
            joining = Mock(send=AsyncMock(), close=AsyncMock())
            await bridge.subscribe(joining, 1)
            self.assertEqual(
                messages(joining),
                [{"type": "historyDownloadsConnection", "market_id": 1, "connected": True}],
            )
        finally:
            await bridge.close()
        redis.aclose.assert_awaited_once()

    async def test_failed_client_does_not_interrupt_healthy_client(self):
        bridge = HistoryDownloadEventBridge(Mock())
        failed = Mock(send=AsyncMock(side_effect=ConnectionError()), close=AsyncMock())
        healthy = Mock(send=AsyncMock(), close=AsyncMock())
        bridge._clients = {failed: {1}, healthy: {1}}
        await bridge._broadcast(changed())
        self.assertNotIn(failed, bridge._clients)
        self.assertEqual(messages(healthy), [changed()])

    async def test_producer_restart_refreshes_all_markets_without_gateway_reconnection(self):
        incoming = asyncio.Queue()
        redis = Mock(
            xrevrange=AsyncMock(return_value=[("10-0", {})]),
            xread=AsyncMock(),
            aclose=AsyncMock(),
        )

        async def read(*args, **kwargs):
            return await incoming.get()

        redis.xread.side_effect = read
        bridge = HistoryDownloadEventBridge(redis)
        first = Mock(send=AsyncMock(), close=AsyncMock())
        second = Mock(send=AsyncMock(), close=AsyncMock())
        await bridge.subscribe(first, 1)
        await bridge.subscribe(first, 2)
        await bridge.subscribe(second, 3)
        bridge.start()

        async def wait_for(predicate):
            async with asyncio.timeout(3):
                while not predicate():
                    await asyncio.sleep(0.01)

        try:
            await wait_for(lambda: redis.xread.await_count == 1)
            unrelated = [
                (f"{11 + index}-0", {"event": json.dumps(changed(1000 + index))})
                for index in range(150)
            ]
            malformed = {
                "event": json.dumps({"type": "historyDownloadsResnapshot", "market_id": 1})
            }
            await incoming.put([("stream", [*unrelated, ("161-0", malformed)])])
            await wait_for(lambda: redis.xread.await_count == 2)
            self.assertEqual(len(messages(first)), 4)
            self.assertEqual(len(messages(second)), 2)

            await incoming.put(
                [("stream", [("162-0", {"event": '{"type":"historyDownloadsResnapshot"}'})])]
            )
            await wait_for(lambda: redis.xread.await_count == 3)
            for client, market_ids in ((first, (1, 2)), (second, (3,))):
                for market_id in market_ids:
                    connected = {
                        "type": "historyDownloadsConnection",
                        "market_id": market_id,
                        "connected": True,
                    }
                    self.assertEqual(messages(client).count(connected), 2)
            self.assertTrue(bridge._connected)
            redis.xrevrange.assert_awaited_once()
        finally:
            await bridge.close()

    def test_malformed_event_is_not_forwarded(self):
        for event in (
            [],
            changed(market_id=True),
            changed(market_id=-1),
            {**changed(), "revision": "2"},
            {**changed(), "type": "other"},
            {**changed(), "job_id": ""},
            {"type": "historyDownloadsResnapshot", "market_id": 1},
            {"type": "historyDownloadsResnapshot", "revision": 2},
        ):
            with self.subTest(event=event):
                self.assertIsNone(
                    HistoryDownloadEventBridge._read_event({"event": json.dumps(event)})
                )
