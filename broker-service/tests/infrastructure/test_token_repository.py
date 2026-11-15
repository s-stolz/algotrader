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


class TokenReplacementRedisTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_compare_and_set_fences_replacement_in_real_redis(self) -> None:
        import asyncio
        import os
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        from redis.asyncio import Redis

        if os.getenv("RUN_BROKER_TOKEN_REDIS_TESTS") != "1":
            self.skipTest("Set RUN_BROKER_TOKEN_REDIS_TESTS=1 for isolated Redis integration")
        executable = shutil.which("redis-server")
        if executable is None:
            self.skipTest("redis-server is required")
        with tempfile.TemporaryDirectory(prefix="broker-token-") as directory:
            socket = str(Path(directory) / "redis.sock")
            process = subprocess.Popen(
                [
                    executable,
                    "--port",
                    "0",
                    "--unixsocket",
                    socket,
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            client = Redis(unix_socket_path=socket)
            try:
                for _ in range(100):
                    if Path(socket).exists():
                        break
                    await asyncio.sleep(0.02)
                await client.ping()
                repository = RedisTokenRepository(client, "test-token")
                original = CtraderTokenState("access", "refresh", 200, 100, "client", "12", "demo")
                refreshed = CtraderTokenState(
                    "rotated", "rotated-refresh", 300, 200, "client", "12", "demo"
                )
                reconnected = CtraderTokenState(
                    "new-grant", "new-refresh", 400, 300, "new-client", "12", "demo"
                )
                await repository.set_current_token(original)
                self.assertTrue(await repository.compare_and_set_current_token(original, refreshed))
                await repository.set_current_token(reconnected)
                self.assertFalse(
                    await repository.compare_and_set_current_token(refreshed, original)
                )
                self.assertEqual(await repository.get_current_token(), reconnected)
            finally:
                await client.aclose()
                process.terminate()
                await asyncio.to_thread(process.wait, timeout=5)
