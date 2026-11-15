from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from app.domain.models import Account
from app.infrastructure.ctrader_oauth_client import RefreshResult
from app.infrastructure.token_repository import CtraderTokenState
from app.onboarding.session import persist_connection, select_account
from app.settings import CtraderCredentials


class OnboardingSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "broker.env"
        self.output.write_text("unchanged\n")
        self.credentials = CtraderCredentials(
            "client", "secret", "demo", "", "", "https://example.com", 120, 10
        )
        self.token = RefreshResult("access", "refresh", 120, 100)

    def test_selection_is_explicit_and_expected_account_is_enforced(self) -> None:
        account = Account(account_id=12, broker_name="Broker", trader_login=99)
        read = Mock(return_value="12")
        announce = Mock()
        selected = select_account([account], "demo", read=read, announce=announce)
        self.assertEqual(selected, account)
        read.assert_called_once()
        self.assertIn("Broker / login 99", announce.call_args.args[0])
        with self.assertRaises(ValueError):
            select_account([account], "demo", expected_account_id="13", read=read)

    async def test_wrong_account_does_not_change_file_or_repository(self) -> None:
        repository = AsyncMock()
        with self.assertRaisesRegex(ValueError, "cannot change"):
            await persist_connection(
                self.output,
                self.credentials,
                self.token,
                Account(account_id=12),
                expected_account_id="13",
                repository=repository,
            )
        self.assertEqual(self.output.read_text(), "unchanged\n")
        repository.set_current_token.assert_not_awaited()

    async def test_wrong_stored_environment_does_not_replace_credentials(self) -> None:
        repository = AsyncMock()
        repository.get_current_token.return_value = CtraderTokenState(
            "old", "old", 200, 100, "client", "12", "live"
        )
        with self.assertRaisesRegex(ValueError, "different broker"):
            await persist_connection(
                self.output,
                self.credentials,
                self.token,
                Account(account_id=12),
                expected_account_id="12",
                repository=repository,
            )
        self.assertEqual(self.output.read_text(), "unchanged\n")
        repository.set_current_token.assert_not_awaited()

    async def test_valid_connection_writes_actual_expiry_and_bound_token_state(self) -> None:
        repository = AsyncMock()
        repository.get_current_token.return_value = None
        await persist_connection(
            self.output,
            self.credentials,
            self.token,
            Account(account_id=12),
            expected_account_id="12",
            repository=repository,
        )
        content = self.output.read_text()
        self.assertIn("CTRADER_ACCESS_TOKEN_ISSUED_AT=100\n", content)
        self.assertIn("CTRADER_ACCESS_TOKEN_EXPIRES_AT=220\n", content)
        self.assertIn("ACCOUNT_ID=12\n", content)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        state = repository.set_current_token.call_args.args[0]
        self.assertEqual(
            (state.client_id, state.account_id, state.environment), ("client", "12", "demo")
        )

    async def test_failed_atomic_file_replace_preserves_previous_file(self) -> None:
        repository = AsyncMock()
        repository.get_current_token.return_value = None
        with patch("app.onboarding.session.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                await persist_connection(
                    self.output,
                    self.credentials,
                    self.token,
                    Account(account_id=12),
                    expected_account_id="12",
                    repository=repository,
                )
        self.assertEqual(self.output.read_text(), "unchanged\n")
        repository.set_current_token.assert_not_awaited()
