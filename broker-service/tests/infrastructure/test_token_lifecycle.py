from __future__ import annotations

import unittest

from app.infrastructure.ctrader_oauth_client import RefreshResult
from app.infrastructure.token_lifecycle import TokenLifecycleManager
from app.infrastructure.token_repository import CtraderTokenState
from app.settings import CtraderCredentials, Settings


class FakeTokenRepository:
    def __init__(self, state: CtraderTokenState | None = None) -> None:
        self.state = state

    async def get_current_token(self) -> CtraderTokenState | None:
        return self.state

    async def set_current_token(self, state: CtraderTokenState) -> None:
        self.state = state

    async def compare_and_set_current_token(
        self, previous: CtraderTokenState, state: CtraderTokenState
    ) -> bool:
        if self.state != previous:
            return False
        self.state = state
        return True


class FakeOAuthClient:
    def __init__(self) -> None:
        self.calls = 0

    async def refresh_access_token(self, refresh_token: str) -> RefreshResult:
        self.calls += 1
        return RefreshResult(
            access_token=f"new-access-{self.calls}",
            refresh_token=f"new-refresh-{self.calls}",
            expires_in=120,
            issued_at=1712340000 + self.calls,
        )


class TokenLifecycleManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_uses_env_when_redis_empty(self) -> None:
        settings = Settings(broker_token_refresh_early_seconds=604800)
        credentials = CtraderCredentials(
            client_id="id",
            secret="secret",
            host_type="demo",
            access_token="env-access",
            refresh_token="env-refresh",
            token_url="https://openapi.ctrader.com/apps/token",
            access_token_expires_in_seconds=2628000,
            token_request_timeout_seconds=10.0,
        )
        repo = FakeTokenRepository()
        oauth = FakeOAuthClient()
        manager = TokenLifecycleManager(settings, credentials, repo, oauth)

        await manager.startup()
        self.assertEqual(manager.get_access_token(), "env-access")
        state = repo.state
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.access_token, "env-access")
        await manager.shutdown()

    async def test_startup_refreshes_immediately_when_due(self) -> None:
        settings = Settings(broker_token_refresh_early_seconds=604800)
        credentials = CtraderCredentials(
            client_id="id",
            secret="secret",
            host_type="demo",
            access_token="env-access",
            refresh_token="env-refresh",
            token_url="https://openapi.ctrader.com/apps/token",
            access_token_expires_in_seconds=60,
            token_request_timeout_seconds=10.0,
        )
        repo = FakeTokenRepository(
            CtraderTokenState(
                access_token="old",
                refresh_token="old-refresh",
                issued_at=100,
                expires_at=101,
            )
        )
        oauth = FakeOAuthClient()
        manager = TokenLifecycleManager(settings, credentials, repo, oauth)

        await manager.startup()

        self.assertEqual(oauth.calls, 1)
        self.assertEqual(manager.get_access_token(), "new-access-1")
        state = repo.state
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.refresh_token, "new-refresh-1")
        await manager.shutdown()


if __name__ == "__main__":
    unittest.main()


class TokenBindingTests(unittest.IsolatedAsyncioTestCase):
    def credentials(self, **changes) -> CtraderCredentials:
        from dataclasses import replace

        return replace(
            CtraderCredentials(
                "client",
                "secret",
                "demo",
                "env-access",
                "env-refresh",
                "https://example.com",
                120,
                10,
                account_id="12",
            ),
            **changes,
        )

    async def test_bootstrap_uses_actual_expiry_instead_of_restart_time(self) -> None:
        repo = FakeTokenRepository()
        manager = TokenLifecycleManager(
            Settings(broker_token_refresh_early_seconds=1),
            self.credentials(access_token_issued_at=100, access_token_expires_at=9999999999),
            repo,
            FakeOAuthClient(),
        )
        await manager.startup()
        assert repo.state is not None
        self.assertEqual((repo.state.issued_at, repo.state.expires_at), (100, 9999999999))
        self.assertEqual(
            (repo.state.client_id, repo.state.account_id, repo.state.environment),
            ("client", "12", "demo"),
        )
        await manager.shutdown()

    async def test_another_application_cannot_reuse_stored_tokens(self) -> None:
        original = CtraderTokenState("old", "old", 9999999999, 100, "other-client", "12", "demo")
        repo = FakeTokenRepository(original)
        manager = TokenLifecycleManager(Settings(), self.credentials(), repo, FakeOAuthClient())
        with self.assertRaisesRegex(RuntimeError, "another connection"):
            await manager.startup()
        self.assertEqual(repo.state, original)

    async def test_refresh_cannot_overwrite_explicit_reconnection(self) -> None:
        from unittest.mock import AsyncMock

        original = CtraderTokenState("old", "old", 1, 0, "client", "12", "demo")
        replacement = CtraderTokenState(
            "new-session", "new-refresh", 9999999999, 100, "client", "12", "demo"
        )
        repo = FakeTokenRepository(original)

        async def refresh(_token):
            repo.state = replacement
            return RefreshResult("stale-access", "stale-refresh", 120, 100)

        oauth = AsyncMock()
        oauth.refresh_access_token.side_effect = refresh
        manager = TokenLifecycleManager(
            Settings(broker_token_refresh_max_retries=0), self.credentials(), repo, oauth
        )
        with self.assertRaisesRegex(RuntimeError, "were replaced"):
            await manager.startup()
        self.assertEqual(repo.state, replacement)
