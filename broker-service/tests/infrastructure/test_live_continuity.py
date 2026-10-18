import asyncio
import unittest
from dataclasses import replace
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from app.domain.models import Symbol, Trendbar
from app.domain.value_objects import AccountId, SymbolDescriptor, SymbolId, Timeframe
from app.infrastructure.ctrader_client import CtraderClient
from app.infrastructure.redis_streams_publisher import RedisStreamsPublisher
from app.infrastructure.trendbar_stream_registry import TrendbarStreamRegistry
from app.settings import Settings
from ctrader_open_api.messages import OpenApiMessages_pb2, OpenApiModelMessages_pb2

ProtoOASpotEvent = getattr(OpenApiMessages_pb2, "ProtoOASpotEvent")
ProtoOATrendbar = getattr(OpenApiModelMessages_pb2, "ProtoOATrendbar")


class LiveContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clients = []
        self.registries = []

    async def asyncTearDown(self):
        for registry in self.registries:
            await registry.shutdown()
        for client in self.clients:
            task = client._subscription_restore_task
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    def client(self, real_subscriptions=False):
        with patch.object(CtraderClient, "_create_client", return_value=Mock()):
            client = CtraderClient(Mock(access_token="test"))
        client._symbol_cache.store_descriptor(SymbolDescriptor(SymbolId(1), "EURUSD", True))
        client._symbol_cache.store_full_symbol(Symbol(1, "EURUSD", 5, 4))
        if not real_subscriptions:
            client._subscribe_spots = AsyncMock()
            client._subscribe_live_trendbar = AsyncMock()
            client._unsubscribe_live_trendbar = AsyncMock()
        self.clients.append(client)
        return client

    async def registry(self, client, redis, queue_size=1000):
        publisher = RedisStreamsPublisher(redis, Settings())
        registry = TrendbarStreamRegistry(
            client.register_trendbar_handler,
            client.unregister_trendbar_handler,
            publisher.publish_candle,
            replace(Settings(), tick_queue_size=queue_size),
        )
        self.registries.append(registry)
        await registry.start_trendbar_stream(AccountId(123), "EURUSD", Timeframe.M1)
        return registry

    def event(self, minute):
        return ProtoOASpotEvent(
            ctidTraderAccountId=123,
            symbolId=1,
            bid=100000,
            trendbar=[
                ProtoOATrendbar(
                    period=1,
                    utcTimestampInMinutes=minute,
                    low=100000,
                    deltaOpen=0,
                    deltaHigh=1,
                    deltaClose=1,
                    volume=1,
                )
            ],
        )

    async def test_queued_old_bars_keep_identity_and_restart_changes_identity_on_stable_key(self):
        client = self.client()
        delivered = []
        entered, release = asyncio.Event(), asyncio.Event()

        async def publish(key, fields, **kwargs):
            if not delivered:
                entered.set()
                await release.wait()
            delivered.append((key, fields))

        redis = Mock(xadd=AsyncMock(side_effect=publish))
        await self.registry(client, redis)
        await client._emit_trendbars(self.event(1))
        await entered.wait()
        await client._emit_trendbars(self.event(2))
        client._on_disconnected(client._client, "brief disconnect")
        await client._emit_trendbars(self.event(3))
        release.set()
        async with asyncio.timeout(1):
            while len(delivered) < 3:
                await asyncio.sleep(0)
        sessions = [fields["continuity"] for _, fields in delivered]
        self.assertEqual(sessions[0], sessions[1])
        self.assertNotEqual(sessions[1], sessions[2])
        self.assertEqual([fields["t"] for _, fields in delivered], ["60000", "120000", "180000"])
        restarted = self.client()
        restarted_redis = Mock(xadd=AsyncMock())
        await self.registry(restarted, restarted_redis)
        await restarted._emit_trendbars(self.event(4))
        async with asyncio.timeout(1):
            while not restarted_redis.xadd.await_count:
                await asyncio.sleep(0)
        key, fields = restarted_redis.xadd.call_args.args
        self.assertEqual(key, "candles:123:EURUSD:M1")
        self.assertTrue(all(key == old_key for old_key, _ in delivered))
        self.assertNotIn(fields["continuity"], sessions)

    async def test_stale_event_waiting_for_handlers_is_discarded_after_disconnect(self):
        client = self.client()
        redis = Mock(xadd=AsyncMock())
        await self.registry(client, redis)
        async with client._trendbar_lock:
            old = asyncio.create_task(client._emit_trendbars(self.event(1)))
            await asyncio.sleep(0)
            client._on_disconnected(client._client, "interrupted dispatch")
        await old
        await client._emit_trendbars(self.event(2))
        async with asyncio.timeout(1):
            while not redis.xadd.await_count:
                await asyncio.sleep(0)
        self.assertEqual(redis.xadd.await_count, 1)
        self.assertEqual(redis.xadd.call_args.args[1]["t"], "120000")

    async def test_failed_stream_start_retries_without_orphan_duplicate_handlers(self):
        client = self.client()
        client._subscribe_live_trendbar = AsyncMock(
            side_effect=[RuntimeError("temporary rejection"), None]
        )
        redis = Mock(xadd=AsyncMock())
        publisher = RedisStreamsPublisher(redis, Settings())
        registry = TrendbarStreamRegistry(
            client.register_trendbar_handler,
            client.unregister_trendbar_handler,
            publisher.publish_candle,
            Settings(),
        )
        self.registries.append(registry)
        with self.assertRaises(RuntimeError):
            await registry.start_trendbar_stream(AccountId(123), "EURUSD", Timeframe.M1)
        status = await registry.start_trendbar_stream(AccountId(123), "EURUSD", Timeframe.M1)
        self.assertTrue(status.running)
        await client._emit_trendbars(self.event(1))
        async with asyncio.timeout(1):
            while not redis.xadd.await_count:
                await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(redis.xadd.await_count, 1)

    async def test_old_subscription_receipt_cannot_mark_new_connection_active(self):
        from ctrader_open_api.messages import OpenApiCommonMessages_pb2
        from twisted.internet.defer import Deferred

        client = self.client(real_subscriptions=True)
        client._loop = asyncio.get_running_loop()
        client._app_authenticated.set()
        redis = Mock(xadd=AsyncMock())
        publisher = RedisStreamsPublisher(redis, Settings())
        registry = TrendbarStreamRegistry(
            client.register_trendbar_handler,
            client.unregister_trendbar_handler,
            publisher.publish_candle,
            Settings(),
        )
        self.registries.append(registry)
        entered = asyncio.Event()
        requests = []
        first = Deferred()
        response = getattr(OpenApiMessages_pb2, "ProtoOAAccountAuthRes")(ctidTraderAccountId=123)
        wrapped = getattr(OpenApiCommonMessages_pb2, "ProtoMessage")(
            payloadType=response.payloadType, payload=response.SerializeToString()
        )

        def send(request, **kwargs):
            requests.append(type(request).__name__)
            if len(requests) == 1:
                entered.set()
                return first
            deferred = Deferred()
            asyncio.get_running_loop().call_soon(deferred.callback, wrapped)
            return deferred

        with patch.object(client._client, "send", side_effect=send):
            starting = asyncio.create_task(
                registry.start_trendbar_stream(AccountId(123), "EURUSD", Timeframe.M1)
            )
            await asyncio.wait_for(entered.wait(), 1)
            client._on_disconnected(client._client, "receipt already queued")
            await asyncio.sleep(0)
            first.callback(wrapped)
            with self.assertRaisesRegex(RuntimeError, "connection changed"):
                await starting
            client._app_authenticated.set()
            await registry.start_trendbar_stream(AccountId(123), "EURUSD", Timeframe.M1)
            await client._emit_trendbars(self.event(1))
            async with asyncio.timeout(1):
                while not redis.xadd.await_count:
                    await asyncio.sleep(0)
            self.assertEqual(requests.count("ProtoOASubscribeSpotsReq"), 2)
            self.assertEqual(requests.count("ProtoOASubscribeLiveTrendbarReq"), 1)
            self.assertEqual(redis.xadd.await_count, 1)
            await registry.shutdown()

    async def test_healthy_market_publishes_through_another_markets_subscription_retries(self):
        from ctrader_open_api.messages import OpenApiCommonMessages_pb2
        from twisted.internet.defer import Deferred

        for rejected_request in (
            "ProtoOASubscribeSpotsReq",
            "ProtoOASubscribeLiveTrendbarReq",
        ):
            with self.subTest(rejected_request=rejected_request):
                client = self.client(real_subscriptions=True)
                client._loop = asyncio.get_running_loop()
                client._app_authenticated.set()
                client._symbol_cache.store_descriptor(SymbolDescriptor(SymbolId(2), "GBPUSD", True))
                client._symbol_cache.store_full_symbol(Symbol(2, "GBPUSD", 5, 4))
                requests, delays = [], []
                subscribed = set()
                failing = False
                real_sleep = asyncio.sleep
                redis = Mock(xadd=AsyncMock())

                def wrap(message):
                    return getattr(OpenApiCommonMessages_pb2, "ProtoMessage")(
                        payloadType=message.payloadType, payload=message.SerializeToString()
                    )

                def send(request, **kwargs):
                    name = type(request).__name__
                    if name == "ProtoOASubscribeSpotsReq":
                        symbol_id = getattr(request, "symbolId")[0]
                    else:
                        symbol_id = getattr(request, "symbolId", None)
                    requests.append((name, symbol_id))
                    if failing and name == rejected_request and symbol_id == 1:
                        response = getattr(OpenApiMessages_pb2, "ProtoOAErrorRes")(
                            errorCode="TEMPORARY"
                        )
                    else:
                        subscribed.add((name, symbol_id))
                        response = getattr(OpenApiMessages_pb2, "ProtoOAAccountAuthRes")(
                            ctidTraderAccountId=123
                        )
                    deferred = Deferred()
                    asyncio.get_running_loop().call_soon(deferred.callback, wrap(response))
                    return deferred

                async def retry(delay):
                    nonlocal failing
                    delays.append(delay)
                    self.assertIn(("ProtoOASubscribeSpotsReq", 2), subscribed)
                    self.assertIn(("ProtoOASubscribeLiveTrendbarReq", 2), subscribed)
                    event = self.event(len(delays))
                    event.symbolId = 2
                    client._on_message(client._client, wrap(event))
                    async with asyncio.timeout(1):
                        while redis.xadd.await_count < len(delays):
                            await real_sleep(0)
                    if len(delays) == 7:
                        failing = False

                with patch.object(client._client, "send", side_effect=send):
                    registry = await self.registry(client, redis)
                    await registry.start_trendbar_stream(AccountId(123), "GBPUSD", Timeframe.M1)
                    requests.clear()
                    subscribed.clear()
                    failing = True
                    with patch(
                        "app.infrastructure.ctrader_client.asyncio.sleep", retry
                    ), self.assertLogs("app.infrastructure.ctrader_client", level="ERROR"):
                        client._on_disconnected(client._client, "both Markets interrupted")
                        client._on_message(
                            client._client,
                            getattr(OpenApiMessages_pb2, "ProtoOAApplicationAuthRes")(),
                        )
                        await real_sleep(0)
                        assert client._subscription_restore_task is not None
                        async with asyncio.timeout(2):
                            await client._subscription_restore_task
                    self.assertEqual(delays, [1, 2, 4, 8, 16, 30, 30])
                    self.assertEqual(requests.count(("ProtoOAAccountAuthReq", None)), 1)
                    self.assertEqual(requests.count(("ProtoOASubscribeSpotsReq", 2)), 1)
                    self.assertEqual(requests.count(("ProtoOASubscribeLiveTrendbarReq", 2)), 1)
                    self.assertEqual(requests.count((rejected_request, 1)), 8)
                    other_request = (
                        "ProtoOASubscribeLiveTrendbarReq"
                        if rejected_request == "ProtoOASubscribeSpotsReq"
                        else "ProtoOASubscribeSpotsReq"
                    )
                    self.assertEqual(requests.count((other_request, 1)), 1)
                    published = [call.args for call in redis.xadd.call_args_list]
                    self.assertEqual([key for key, _ in published], ["candles:123:GBPUSD:M1"] * 7)
                    self.assertEqual(
                        [fields["t"] for _, fields in published],
                        ["60000", "120000", "180000", "240000", "300000", "360000", "420000"],
                    )
                    self.assertEqual(len({fields["continuity"] for _, fields in published}), 1)
                    await registry.shutdown()

    async def test_direct_live_publication_without_identity_fails_closed(self):
        redis = Mock(xadd=AsyncMock())
        publisher = RedisStreamsPublisher(redis, Settings())
        bar = Trendbar(*(Decimal("1") for _ in range(4)), v=1, t=60000)
        with self.assertRaises(ValueError):
            await publisher.publish_candle(AccountId(1), "EURUSD", Timeframe.M1, bar)
        redis.xadd.assert_not_awaited()

    async def test_overflow_is_observed_before_next_publication_without_disconnect(self):
        client = self.client()
        delivered = []
        entered, release = asyncio.Event(), asyncio.Event()

        async def publish(key, fields, **kwargs):
            if not delivered:
                entered.set()
                await release.wait()
            delivered.append(fields)

        await self.registry(client, Mock(xadd=AsyncMock(side_effect=publish)), queue_size=1)
        await client._emit_trendbars(self.event(1))
        await entered.wait()
        # Independent event tasks overflow twice while the first XADD is active.
        await asyncio.gather(*(client._emit_trendbars(self.event(m)) for m in (2, 3, 4)))
        release.set()
        async with asyncio.timeout(1):
            while len(delivered) < 2:
                await asyncio.sleep(0)
        await client._emit_trendbars(self.event(5))
        async with asyncio.timeout(1):
            while len(delivered) < 3:
                await asyncio.sleep(0)
        self.assertEqual([d["t"] for d in delivered], ["60000", "240000", "300000"])
        self.assertNotEqual(delivered[0]["continuity"], delivered[1]["continuity"])
        self.assertEqual(delivered[1]["continuity"], delivered[2]["continuity"])

    async def test_failed_publications_retry_and_protect_old_queued_bars(self):
        client = self.client()
        delivered, attempts = [], []
        failed, release = asyncio.Event(), asyncio.Event()
        real_sleep = asyncio.sleep

        async def retry(_delay):
            failed.set()
            await release.wait()
            await real_sleep(0)

        async def publish(key, fields, **kwargs):
            attempts.append(fields)
            if len(attempts) in (2, 3):
                raise OSError("Redis unavailable")
            delivered.append(fields)

        await self.registry(client, Mock(xadd=AsyncMock(side_effect=publish)))
        await client._emit_trendbars(self.event(1))
        async with asyncio.timeout(1):
            while not delivered:
                await real_sleep(0)
        with patch("app.infrastructure.trendbar_stream_registry.asyncio.sleep", retry):
            await client._emit_trendbars(self.event(2))
            await failed.wait()
            await client._emit_trendbars(self.event(3))
            release.set()
            async with asyncio.timeout(1):
                while len(delivered) < 3:
                    await real_sleep(0)
        self.assertEqual([d["t"] for d in delivered], ["60000", "120000", "180000"])
        self.assertNotEqual(delivered[0]["continuity"], delivered[1]["continuity"])
        self.assertEqual(delivered[1]["continuity"], delivered[2]["continuity"])
        self.assertNotEqual(attempts[2]["continuity"], delivered[1]["continuity"])
