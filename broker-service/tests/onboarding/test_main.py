from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.onboarding.__main__ import authorize
from app.onboarding.callback import AuthorizationCallback


class AuthorizationFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_exchange_does_not_discover_accounts_or_replace_existing_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "broker.env"
            output.write_text("existing\n")
            args = argparse.Namespace(
                scope="accounts",
                output=str(output),
                bind_address="127.0.0.1",
                expected_account_id="12",
                replace_token_state=True,
                account_id="12",
            )
            with (
                patch.dict(
                    "os.environ",
                    {
                        "CTRADER_CLIENT_ID": "client",
                        "CTRADER_SECRET": "secret",
                        "CTRADER_HOST_TYPE": "demo",
                    },
                ),
                patch(
                    "app.onboarding.__main__.wait_for_callback",
                    return_value=AuthorizationCallback("code"),
                ),
                patch(
                    "app.onboarding.__main__.CtraderOAuthClient.exchange_authorization_code",
                    side_effect=RuntimeError("exchange failed"),
                ),
                patch(
                    "app.onboarding.__main__.discover_accounts", new_callable=AsyncMock
                ) as discover,
                patch("builtins.print"),
            ):
                with self.assertRaisesRegex(RuntimeError, "exchange failed"):
                    await authorize(args)
            discover.assert_not_awaited()
            self.assertEqual(output.read_text(), "existing\n")
