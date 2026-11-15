from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Callable

from app.domain.models import Account
from app.infrastructure.ctrader_client import CtraderClient
from app.infrastructure.ctrader_oauth_client import RefreshResult
from app.infrastructure.token_repository import CtraderTokenState, RedisTokenRepository
from app.settings import CtraderCredentials


def select_account(
    accounts: list[Account],
    environment: str,
    *,
    expected_account_id: str | None = None,
    requested_account_id: str | None = None,
    read: Callable[[str], str] = input,
    announce: Callable[[str], None] = print,
) -> Account:
    candidates = [account for account in accounts if account.is_live == (environment == "live")]
    if expected_account_id is not None:
        candidates = [
            account for account in candidates if str(account.account_id) == expected_account_id
        ]
    if not candidates:
        raise ValueError(
            "The expected broker account was not authorized; existing configuration is unchanged"
        )
    if requested_account_id is not None:
        selected = next(
            (account for account in candidates if str(account.account_id) == requested_account_id),
            None,
        )
        if selected is None:
            raise ValueError(
                "Selected account does not match an authorized account for this installation"
            )
        return selected
    return _prompt_account(candidates, environment, read, announce)


def _prompt_account(
    candidates: list[Account],
    environment: str,
    read: Callable[[str], str],
    announce: Callable[[str], None],
) -> Account:
    for number, account in enumerate(candidates, start=1):
        announce(
            f"{number}. {account.broker_name or 'Broker'} / "
            f"login {account.trader_login or account.account_id} ({environment})"
        )
    while True:
        if len(candidates) == 1:
            choice = read("Connect to this account? [Y/n]: ").strip().lower()
            if choice in ("", "y", "yes"):
                return candidates[0]
            if choice in ("n", "no"):
                raise ValueError("Account selection cancelled. Run setup again when ready.")
            announce("Enter Y to connect or N to cancel.")
        else:
            choice = read(f"Select an account [1-{len(candidates)}], or q to cancel: ").strip()
            if choice.lower() == "q":
                raise ValueError("Account selection cancelled. Run setup again when ready.")
            choices = {str(number): account for number, account in enumerate(candidates, start=1)}
            if choice in choices:
                return choices[choice]
            announce(f"Enter a number from 1 to {len(candidates)}, or q to cancel.")


async def discover_accounts(credentials: CtraderCredentials) -> list[Account]:
    client = CtraderClient(credentials)
    try:
        await asyncio.wait_for(client.connect(), timeout=45)
        return await asyncio.wait_for(client.list_accounts(), timeout=45)
    except Exception:
        raise RuntimeError(
            "Broker account verification failed; "
            "check the application credentials and authorization"
        ) from None
    finally:
        await client.disconnect()


def token_state(
    credentials: CtraderCredentials, token: RefreshResult, account_id: str
) -> CtraderTokenState:
    return CtraderTokenState(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        expires_at=token.issued_at + token.expires_in,
        issued_at=token.issued_at,
        client_id=credentials.client_id,
        account_id=account_id,
        environment=credentials.host_type,
    )


def write_credentials(
    path: Path, credentials: CtraderCredentials, state: CtraderTokenState
) -> None:
    values = {
        "CTRADER_CLIENT_ID": credentials.client_id,
        "CTRADER_SECRET": credentials.secret,
        "CTRADER_HOST_TYPE": credentials.host_type,
        "CTRADER_ACCESS_TOKEN": state.access_token,
        "CTRADER_REFRESH_TOKEN": state.refresh_token,
        "CTRADER_ACCESS_TOKEN_ISSUED_AT": str(state.issued_at),
        "CTRADER_ACCESS_TOKEN_EXPIRES_AT": str(state.expires_at),
        "ACCOUNT_ID": state.account_id,
    }
    if any("\n" in value or "\r" in value or "\x00" in value for value in values.values()):
        raise ValueError("Broker credentials contain unsupported control characters")
    if path.is_symlink():
        raise ValueError("Credential output must not be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".broker-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write("".join(f"{name}={value}\n" for name, value in values.items()))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def persist_connection(
    output: Path,
    credentials: CtraderCredentials,
    token: RefreshResult,
    selected: Account,
    *,
    expected_account_id: str | None = None,
    repository: RedisTokenRepository | None = None,
) -> None:
    account_id = str(selected.account_id)
    if expected_account_id is not None and expected_account_id != account_id:
        raise ValueError("Reconnect cannot change the installation account")
    if selected.is_live != (credentials.host_type == "live"):
        raise ValueError("Reconnect cannot change the broker environment")
    state = token_state(credentials, token, account_id)
    if repository is not None:
        if expected_account_id is None:
            raise ValueError("Token replacement requires the existing account ID")
        current = await repository.get_current_token()
        if current is not None and (
            (current.account_id and current.account_id != account_id)
            or (current.environment and current.environment != credentials.host_type)
        ):
            raise ValueError(
                "Stored credentials belong to a different broker account or environment"
            )
    write_credentials(output, credentials, state)
    if repository is not None:
        await repository.set_current_token(state)


def authorized_credentials(
    credentials: CtraderCredentials, token: RefreshResult
) -> CtraderCredentials:
    return replace(
        credentials,
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        access_token_issued_at=token.issued_at,
        access_token_expires_at=token.issued_at + token.expires_in,
    )
