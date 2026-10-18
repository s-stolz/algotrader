from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.domain.value_objects import Timeframe
from app.infrastructure.ctrader_client import CtraderClient
from app.settings import CtraderCredentials
from ctrader_open_api.messages import OpenApiMessages_pb2
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthRes,
    ProtoOAErrorRes,
    ProtoOASymbolsListRes,
)

ProtoOAApplicationAuthRes = getattr(OpenApiMessages_pb2, "ProtoOAApplicationAuthRes")


class CtraderClientAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        credentials = CtraderCredentials(
            client_id="id",
            secret="secret",
            host_type="demo",
            access_token="access",
            refresh_token="refresh",
            token_url="https://example.com/token",
            access_token_expires_in_seconds=2628000,
            token_request_timeout_seconds=10.0,
        )
        with patch.object(CtraderClient, "_create_client"):
            self.client = CtraderClient(credentials)

    async def test_stream_start_preserves_auth_failure_and_does_not_cache_success(self) -> None:
        send = AsyncMock(
            side_effect=[
                ProtoOAErrorRes(
                    errorCode="CH_ACCESS_TOKEN_INVALID", description="Access token is invalid"
                ),
                ProtoOAErrorRes(
                    errorCode="INVALID_REQUEST", description="Trading account is not authorized"
                ),
            ]
        )
        with patch.object(self.client, "_send_request", send):
            with self.assertRaisesRegex(RuntimeError, "CH_ACCESS_TOKEN_INVALID"):
                await self.client.register_trendbar_handler(
                    123, "BTCUSD", Timeframe.M1, AsyncMock()
                )
        self.assertNotIn(123, self.client._authorized_accounts)
        self.assertEqual(send.await_count, 1)

    async def test_failed_authorization_can_be_retried_and_success_is_cached(self) -> None:
        send = AsyncMock(
            side_effect=[
                ProtoOAErrorRes(errorCode="CH_ACCESS_TOKEN_INVALID"),
                ProtoOAAccountAuthRes(ctidTraderAccountId=123),
            ]
        )
        with patch.object(self.client, "_send_request", send):
            with self.assertRaisesRegex(RuntimeError, "CH_ACCESS_TOKEN_INVALID"):
                await self.client._authorize_account(123)
            await self.client._authorize_account(123)
            await self.client._authorize_account(123)
        self.assertEqual(send.await_count, 2)
        self.assertIn(123, self.client._authorized_accounts)

    async def test_unexpected_response_does_not_authorize_account(self) -> None:
        for response in (
            ProtoOAAccountAuthRes(ctidTraderAccountId=456),
            ProtoOASymbolsListRes(ctidTraderAccountId=123),
        ):
            with self.subTest(response=type(response).__name__):
                with patch.object(self.client, "_send_request", AsyncMock(return_value=response)):
                    with self.assertRaisesRegex(RuntimeError, "Unexpected.*authorization response"):
                        await self.client._authorize_account(123)
                self.assertNotIn(123, self.client._authorized_accounts)


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.object(CtraderClient, "_create_client", return_value=Mock()):
            self.client = CtraderClient(
                Mock(access_token="synthetic", client_id="test", secret="test")
            )
        self.client._loop = asyncio.get_running_loop()

    async def asyncTearDown(self):
        for task in (self.client._subscription_restore_task, self.client._application_auth_task):
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_real_callbacks_restore_auth_spots_then_candles_after_brief_disconnect(self):
        self.client._app_authenticated.set()
        self.client._authorized_accounts.add(123)
        self.client._tick_handlers[(123, 1)] = {"tick": AsyncMock()}
        self.client._trendbar_handlers[(123, 1, "M1")] = {"bar": AsyncMock()}
        self.client._active_tick_streams.add((123, 1))
        self.client._active_trendbar_streams.add((123, 1, "M1"))
        requests = []

        async def respond(request):
            requests.append(type(request).__name__)
            return ProtoOAAccountAuthRes(ctidTraderAccountId=123)

        with patch.object(self.client, "_send_request", side_effect=respond):
            self.client._on_disconnected(self.client._client, "brief outage")
            self.client._on_message(self.client._client, ProtoOAApplicationAuthRes())
            for _ in range(20):
                await asyncio.sleep(0)
        self.assertEqual(
            requests,
            [
                "ProtoOAAccountAuthReq",
                "ProtoOASubscribeSpotsReq",
                "ProtoOASubscribeLiveTrendbarReq",
            ],
        )
        self.assertTrue(self.client.is_connected)

    async def test_rejected_subscription_retries_without_duplicate_successful_spots(self):
        self.client._app_authenticated.set()
        self.client._trendbar_handlers[(123, 1, "M1")] = {"bar": AsyncMock()}
        requests = []

        async def respond(request):
            name = type(request).__name__
            requests.append(name)
            if name == "ProtoOASubscribeLiveTrendbarReq" and requests.count(name) == 1:
                return ProtoOAErrorRes(errorCode="TEMPORARY")
            return ProtoOAAccountAuthRes(ctidTraderAccountId=123)

        with patch.object(self.client, "_send_request", side_effect=respond), patch(
            "app.infrastructure.ctrader_client.asyncio.sleep", AsyncMock()
        ), self.assertLogs("app.infrastructure.ctrader_client", level="ERROR"):
            self.client._on_message(self.client._client, ProtoOAApplicationAuthRes())
            await self._finish_restoration()
        self.assertEqual(requests.count("ProtoOASubscribeSpotsReq"), 1)
        self.assertEqual(requests.count("ProtoOASubscribeLiveTrendbarReq"), 2)

    async def _finish_restoration(self):
        # Application-auth callback is delivered on the owning event loop.
        await asyncio.get_running_loop().run_in_executor(None, lambda: None)
        assert self.client._subscription_restore_task is not None
        await self.client._subscription_restore_task

    async def test_application_auth_rejection_retries_on_same_connection(self):
        from importlib import import_module

        common_messages = import_module("ctrader_open_api.messages.OpenApiCommonMessages_pb2")

        proto_message_type = getattr(common_messages, "ProtoMessage")
        from twisted.internet.defer import Deferred

        responses = [ProtoOAErrorRes(errorCode="TEMPORARY"), ProtoOAApplicationAuthRes()]
        requests = []
        delays = []
        original_sleep = asyncio.sleep

        def send(request):
            requests.append(type(request).__name__)
            response = responses.pop(0)
            wrapped = proto_message_type(
                payloadType=response.payloadType, payload=response.SerializeToString()
            )
            deferred = Deferred()
            asyncio.get_running_loop().call_soon(
                self.client._on_message, self.client._client, wrapped
            )
            asyncio.get_running_loop().call_soon(deferred.callback, wrapped)
            return deferred

        async def retry(delay):
            delays.append(delay)
            await original_sleep(0)

        with patch.object(self.client._client, "send", side_effect=send), patch(
            "app.infrastructure.ctrader_client.asyncio.sleep", retry
        ), self.assertLogs("app.infrastructure.ctrader_client", level="ERROR"):
            self.client._on_connected(self.client._client)
            async with asyncio.timeout(1):
                while not self.client.is_connected:
                    await original_sleep(0)
                assert self.client._application_auth_task is not None
                await self.client._application_auth_task
        self.assertEqual(requests, ["ProtoOAApplicationAuthReq", "ProtoOAApplicationAuthReq"])
        self.assertEqual(delays, [1])

    async def test_failed_auth_does_not_cache_account(self):
        for response in (
            ProtoOAErrorRes(errorCode="DENIED"),
            ProtoOAAccountAuthRes(ctidTraderAccountId=456),
        ):
            with patch.object(self.client, "_send_request", AsyncMock(return_value=response)):
                with self.assertRaises(RuntimeError):
                    await self.client._authorize_account(123)
            self.assertNotIn(123, self.client._authorized_accounts)

    async def test_new_disconnect_cancels_restoration_and_clears_active_flags(self):
        self.client._app_authenticated.set()
        self.client._trendbar_handlers[(123, 1, "M1")] = {"bar": AsyncMock()}
        entered = asyncio.Event()

        async def stalled(_request):
            entered.set()
            await asyncio.Event().wait()

        with patch.object(self.client, "_send_request", side_effect=stalled):
            self.client._on_message(self.client._client, ProtoOAApplicationAuthRes())
            await asyncio.wait_for(entered.wait(), 1)
            task = self.client._subscription_restore_task
            assert task is not None
            self.client._on_disconnected(self.client._client, "second outage")
            await asyncio.sleep(0)
            await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(task.cancelled())
        self.assertFalse(self.client.is_connected)
        self.assertFalse(self.client._active_tick_streams)
        self.assertFalse(self.client._active_trendbar_streams)


if __name__ == "__main__":
    unittest.main()
