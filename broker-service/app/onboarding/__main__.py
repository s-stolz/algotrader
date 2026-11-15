from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from redis.asyncio import Redis

from app.infrastructure.ctrader_oauth_client import CtraderOAuthClient
from app.infrastructure.token_repository import RedisTokenRepository
from app.onboarding.callback import REDIRECT_URI, CallbackSession, wait_for_callback
from app.onboarding.session import (
    authorized_credentials,
    discover_accounts,
    persist_connection,
    select_account,
)
from app.settings import CtraderCredentials, Settings


async def authorize(args: argparse.Namespace) -> None:
    credentials = CtraderCredentials.from_env(require_tokens=False)
    if not credentials.client_id.strip() or not credentials.secret.strip():
        raise ValueError("Enter credentials for your approved cTrader application")
    if args.replace_token_state and not args.expected_account_id:
        raise ValueError("Reconnect requires --expected-account-id")
    print(f"Register this exact redirect URI in your cTrader application: {REDIRECT_URI}")
    session = CallbackSession(credentials.client_id, args.scope)
    callback = await asyncio.to_thread(wait_for_callback, session, bind_address=args.bind_address)
    token = await CtraderOAuthClient(credentials).exchange_authorization_code(
        callback.code, REDIRECT_URI
    )
    accounts = await discover_accounts(authorized_credentials(credentials, token))
    selected = select_account(
        accounts,
        credentials.host_type,
        expected_account_id=args.expected_account_id,
        requested_account_id=args.account_id,
    )
    redis = None
    repository = None
    if args.replace_token_state:
        settings = Settings.from_env()
        redis = Redis.from_url(settings.redis_url)
        repository = RedisTokenRepository(redis, settings.broker_token_redis_key)
    try:
        await persist_connection(
            Path(args.output),
            credentials,
            token,
            selected,
            expected_account_id=args.expected_account_id,
            repository=repository,
        )
    finally:
        if redis is not None:
            await redis.aclose()
    print("Broker authorization saved. Return to setup to start the application.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize a local AlgoTrader broker connection")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("authorize")
    command.add_argument("--scope", choices=("accounts", "trading"), default="accounts")
    command.add_argument("--output", required=True)
    command.add_argument("--bind-address", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    command.add_argument("--account-id")
    command.add_argument("--expected-account-id")
    command.add_argument("--replace-token-state", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(authorize(args))
    except (ValueError, RuntimeError, TimeoutError) as exc:
        print(f"Authorization not completed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        print("Authorization cancelled.", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            "Authorization could not be saved. Check local storage and Redis, then retry setup.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
