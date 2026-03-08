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
        self.assertIsNotNone(repo.state)
        self.assertEqual(repo.state.access_token, "env-access")
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
        self.assertIsNotNone(repo.state)
        self.assertEqual(repo.state.refresh_token, "new-refresh-1")
        await manager.shutdown()


if __name__ == "__main__":
    unittest.main()
