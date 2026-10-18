"""Controlled broker publisher for isolated recovery process acceptance."""

import asyncio
import json
import os
import sys
from decimal import Decimal

from app.domain.models import Trendbar
from app.domain.value_objects import AccountId, Timeframe
from app.infrastructure.redis_streams_publisher import RedisStreamsPublisher
from app.infrastructure.stream_registry import TrendbarSubscription
from app.infrastructure.trendbar_stream_registry import TrendbarStreamRegistry
from app.settings import Settings
from redis.asyncio import Redis


async def main():  # noqa: C901
    account, symbol, scenario = sys.argv[1:]
    redis = Redis.from_url(os.environ["RECOVERY_TEST_REDIS_URL"])
    settings = Settings(tick_queue_size=1 if scenario == "queue-overflow" else 1000)
    publisher = RedisStreamsPublisher(redis, settings)
    delivered = []
    entered, release = asyncio.Event(), asyncio.Event()
    faults = {"remaining": 0, "block": False}
    handler = None

    async def subscribe(account_id, name, timeframe, callback):
        nonlocal handler
        handler = callback
        return TrendbarSubscription(account_id, name, 1, timeframe, "test")

    async def unsubscribe(_subscription):
        pass

    async def publish(*args):
        if faults["remaining"]:
            faults["remaining"] -= 1
            entered.set()
            raise ConnectionError("controlled failed Redis publication")
        if faults["block"]:
            faults["block"] = False
            entered.set()
            await release.wait()
        await publisher.publish_candle(*args)
        delivered.append(args[-1])

    registry = TrendbarStreamRegistry(subscribe, unsubscribe, publish, settings)
    await registry.start_trendbar_stream(AccountId(int(account)), symbol, Timeframe.M1)

    async def emit(timestamp):
        assert handler is not None
        await handler(
            Trendbar(
                *(Decimal("1") for _ in range(4)),
                v=1,
                t=timestamp,
                continuity="unchanged-broker-connection",
            )
        )

    async def drain(count):
        async with asyncio.timeout(10):
            while len(delivered) < count:
                await asyncio.sleep(0.001)

    try:
        while line := await asyncio.to_thread(sys.stdin.readline):
            command = json.loads(line)
            timestamp = command["timestamp"]
            before = len(delivered)
            if command["action"] == "prime":
                await emit(timestamp)
                await drain(before + 1)
                await emit(timestamp + 60000)
                await drain(before + 2)
            else:
                faults["remaining"] = 2 if scenario == "publication-loss" else 0
                faults["block"] = scenario == "queue-overflow"
                await emit(timestamp)
                await entered.wait()
                await asyncio.gather(emit(timestamp + 60000), emit(timestamp + 120000))
                release.set()
                await drain(before + (2 if scenario == "queue-overflow" else 3))
                if scenario == "queue-overflow":
                    await emit(timestamp + 180000)
                    await drain(before + 3)
            print(json.dumps({"delivered": len(delivered)}), flush=True)
    finally:
        await registry.shutdown()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
