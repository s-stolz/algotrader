from __future__ import annotations

import unittest
from unittest.mock import patch

from app.infrastructure.ctrader_oauth_client import CtraderOAuthClient
from app.settings import CtraderCredentials


class CtraderOAuthClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_preserves_broker_error_code(self) -> None:
        client = CtraderOAuthClient(
            CtraderCredentials(
                client_id="id",
                secret="secret",
                host_type="demo",
                access_token="access",
                refresh_token="refresh",
                token_url="https://example.com/token",
                access_token_expires_in_seconds=2628000,
                token_request_timeout_seconds=10.0,
            )
        )
        with patch.object(
            client,
            "_refresh_request",
            return_value={"errorCode": "ACCESS_DENIED", "description": "Access denied."},
        ):
            with self.assertRaisesRegex(RuntimeError, "Token refresh failed.*ACCESS_DENIED"):
                await client.refresh_access_token("refresh")
