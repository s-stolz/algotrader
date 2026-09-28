from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.domain.value_objects import Timeframe
from app.infrastructure.ctrader_client import CtraderClient
from app.settings import CtraderCredentials
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthRes,
    ProtoOAErrorRes,
    ProtoOASymbolsListRes,
)


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
