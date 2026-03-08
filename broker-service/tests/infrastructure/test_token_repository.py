from __future__ import annotations

import unittest

from app.infrastructure.token_repository import CtraderTokenState, RedisTokenRepository


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = {}

    async def hgetall(self, key: str):
        return self.data.get(key, {})

    async def hset(self, key: str, mapping: dict[str, str]):
        self.data[key] = dict(mapping)


class RedisTokenRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip(self) -> None:
        redis = FakeRedis()
        repo = RedisTokenRepository(redis, "broker:auth:ctrader:current")

        state = CtraderTokenState(
            access_token="abc",
            refresh_token="ref",
            expires_at=1712345678,
            issued_at=1712340000,
        )
        await repo.set_current_token(state)

        loaded = await repo.get_current_token()
        self.assertEqual(loaded, state)

    async def test_returns_none_when_hash_missing(self) -> None:
        redis = FakeRedis()
        repo = RedisTokenRepository(redis, "missing")

        loaded = await repo.get_current_token()
        self.assertIsNone(loaded)


if __name__ == "__main__":
    unittest.main()
