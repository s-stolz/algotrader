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

    def test_single_account_accepts_enter_as_confirmation(self) -> None:
        account = Account(account_id=12, broker_name="Broker", trader_login=99)
        read = Mock(return_value="")
        announce = Mock()
        selected = select_account([account], "demo", read=read, announce=announce)
        self.assertEqual(selected, account)
        read.assert_called_once_with("Connect to this account? [Y/n]: ")
        self.assertIn("Broker / login 99 (demo)", announce.call_args.args[0])

    def test_single_account_rejection_cancels(self) -> None:
        for answer in ("n", " NO "):
            with self.subTest(answer=answer):
                with self.assertRaisesRegex(ValueError, "selection cancelled"):
                    select_account(
                        [Account(account_id=12)],
                        "demo",
                        read=Mock(return_value=answer),
                        announce=Mock(),
                    )

    def test_invalid_confirmation_reprompts_without_selecting(self) -> None:
        read = Mock(side_effect=["12", "maybe", " Y "])
        announce = Mock()
        account = Account(account_id=12)
        self.assertEqual(select_account([account], "demo", read=read, announce=announce), account)
        self.assertEqual(read.call_count, 3)
        self.assertEqual(announce.call_args.args[0], "Enter Y to connect or N to cancel.")

    def test_multiple_accounts_are_selected_by_menu_number(self) -> None:
        accounts = [
            Account(account_id=12, broker_name="First", trader_login=99),
            Account(account_id=42, broker_name="Second", trader_login=88),
        ]
        read = Mock(side_effect=["", "0", "3", "42", "invalid", " 2 "])
        announce = Mock()
        self.assertEqual(
            select_account(accounts, "demo", read=read, announce=announce), accounts[1]
        )
        self.assertEqual(read.call_count, 6)
        self.assertEqual(announce.call_args_list[0].args[0], "1. First / login 99 (demo)")
        self.assertEqual(announce.call_args_list[1].args[0], "2. Second / login 88 (demo)")

    def test_multiple_account_selection_can_be_cancelled(self) -> None:
        with self.assertRaisesRegex(ValueError, "selection cancelled"):
            select_account(
                [Account(account_id=12), Account(account_id=42)],
                "demo",
                read=Mock(return_value=" Q "),
                announce=Mock(),
            )

    def test_only_accounts_in_selected_environment_are_offered(self) -> None:
        demo = Account(account_id=12)
        live = Account(account_id=42, is_live=True)
        for environment, expected in (("demo", demo), ("live", live)):
            with self.subTest(environment=environment):
                read = Mock(return_value="")
                announce = Mock()
                self.assertEqual(
                    select_account([demo, live], environment, read=read, announce=announce),
                    expected,
                )
                announce.assert_called_once()
                self.assertIn(
                    f"login {expected.account_id} ({environment})", announce.call_args.args[0]
                )
                self.assertIn("[Y/n]", read.call_args.args[0])

    def test_reconnect_only_offers_expected_account(self) -> None:
        accounts = [Account(account_id=12), Account(account_id=42)]
        announce = Mock()
        selected = select_account(
            accounts,
            "demo",
            expected_account_id="42",
            read=Mock(return_value=""),
            announce=announce,
        )
        self.assertEqual(selected, accounts[1])
        announce.assert_called_once()
        self.assertIn("login 42", announce.call_args.args[0])

    def test_missing_account_fails_before_prompting(self) -> None:
        for accounts, expected in (
            ([], None),
            ([Account(account_id=12, is_live=True)], None),
            ([Account(account_id=12)], "42"),
        ):
            with self.subTest(accounts=accounts, expected=expected):
                read = Mock()
                with self.assertRaisesRegex(ValueError, "not authorized"):
                    select_account(accounts, "demo", expected_account_id=expected, read=read)
                read.assert_not_called()

    def test_explicit_account_id_selects_without_prompt(self) -> None:
        accounts = [Account(account_id=12), Account(account_id=42)]
        read = Mock()
        self.assertEqual(
            select_account(accounts, "demo", requested_account_id="42", read=read), accounts[1]
        )
        read.assert_not_called()

    def test_explicit_id_cannot_select_menu_number_or_bypass_binding(self) -> None:
        for requested, expected in (("2", None), ("42", "12"), ("99", None), ("", None)):
            with self.subTest(requested=requested, expected=expected):
                read = Mock()
                with self.assertRaisesRegex(ValueError, "does not match"):
                    select_account(
                        [
                            Account(account_id=12),
                            Account(account_id=42),
                            Account(account_id=99, is_live=True),
                        ],
                        "demo",
                        requested_account_id=requested,
                        expected_account_id=expected,
                        read=read,
                    )
                read.assert_not_called()

    def test_interrupted_prompt_propagates_to_command_cancellation_handler(self) -> None:
        for error in (EOFError, KeyboardInterrupt):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    select_account(
                        [Account(account_id=12)],
                        "demo",
                        read=Mock(side_effect=error),
                        announce=Mock(),
                    )

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
