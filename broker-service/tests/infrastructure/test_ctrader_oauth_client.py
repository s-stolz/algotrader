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

    async def test_documented_get_request_and_camel_case_response(self) -> None:
        from unittest.mock import MagicMock
        from urllib.parse import parse_qs, urlsplit

        client = CtraderOAuthClient(
            CtraderCredentials("id", "secret", "demo", "a", "r", "https://example.com/token", 1, 10)
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"accessToken":"new","refreshToken":"rotated","expiresIn":120}'
        )
        with patch(
            "app.infrastructure.ctrader_oauth_client.request.urlopen", return_value=response
        ) as send:
            result = await client.refresh_access_token("old")
        req = send.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertIsNone(req.data)
        self.assertEqual(
            parse_qs(urlsplit(req.full_url).query),
            {
                "grant_type": ["refresh_token"],
                "refresh_token": ["old"],
                "client_id": ["id"],
                "client_secret": ["secret"],
            },
        )
        self.assertEqual(
            (result.access_token, result.refresh_token, result.expires_in), ("new", "rotated", 120)
        )

    async def test_http_error_does_not_expose_credentials(self) -> None:
        from email.message import Message
        from io import BytesIO
        from urllib.error import HTTPError

        client = CtraderOAuthClient(
            CtraderCredentials("id", "secret", "demo", "a", "r", "https://example.com/token", 1, 10)
        )
        error = HTTPError(
            "https://example.com/?client_secret=secret",
            400,
            "secret",
            Message(),
            BytesIO(b"secret"),
        )
        with patch("app.infrastructure.ctrader_oauth_client.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, r"^Token request failed \(HTTP 400\)$"):
                await client.refresh_access_token("old")

    async def test_nonpositive_expiry_rejected(self) -> None:
        client = CtraderOAuthClient(
            CtraderCredentials("id", "secret", "demo", "a", "r", "https://example.com/token", 1, 10)
        )
        with patch.object(
            client, "_refresh_request", return_value={"accessToken": "a", "expiresIn": 0}
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid expires_in"):
                await client.refresh_access_token("old")
