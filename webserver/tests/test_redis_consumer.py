from __future__ import annotations

import sys
import types
import unittest

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
setattr(redis_asyncio_module, "Redis", object)
setattr(redis_module, "asyncio", redis_asyncio_module)
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)

from app.redis_consumer import RedisConsumer  # noqa: E402


class RedisConsumerTests(unittest.TestCase):
    def test_redis_socket_timeout_exceeds_block_window(self) -> None:
        timeout = RedisConsumer._redis_socket_timeout_seconds(block_ms=5000)

        self.assertEqual(timeout, 6.0)

    def test_redis_socket_timeout_allows_indefinite_block(self) -> None:
        timeout = RedisConsumer._redis_socket_timeout_seconds(block_ms=0)

        self.assertIsNone(timeout)


if __name__ == "__main__":
    unittest.main()
