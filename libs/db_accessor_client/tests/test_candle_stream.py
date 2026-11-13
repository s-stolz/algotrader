import json
import unittest
from contextlib import aclosing

import httpx
from db_accessor_client import (
    AsyncDatabaseAccessorClient,
    DatabaseAccessorClient,
    DatabaseAccessorClientError,
)


def body(complete=True):
    return (
        json.dumps({"type": "candles", "candles": [{"timestamp_ms": 0, "close": 1}]})
        + "\n"
        + ('{"type":"complete"}\n' if complete else "")
    ).encode()


class CandleStreamTests(unittest.TestCase):
    def test_sync_requires_completion(self):
        with DatabaseAccessorClient() as client:
            client.client.close()
            client.client = httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=body(False))
                )
            )
            with self.assertRaisesRegex(DatabaseAccessorClientError, "Incomplete"):
                list(client.stream_candles(symbol="EURUSD", timeframe="M1", start_ms=0, end_ms=1))


class AsyncCandleStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_parses_and_closes_on_cancellation(self):
        closed = []

        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                wire = body()
                yield wire[:12]
                yield wire[12:]

            async def aclose(self):
                closed.append(True)

        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Body()))
            )
            async with aclosing(
                client.stream_candles(symbol="EURUSD", timeframe="M1", start_ms=0, end_ms=1)
            ) as batches:
                self.assertEqual(await anext(batches), [{"timestamp_ms": 0, "close": 1}])
            self.assertEqual(closed, [True])

    async def test_async_requires_terminal_frame(self):
        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=body(False))
                )
            )
            with self.assertRaisesRegex(DatabaseAccessorClientError, "Incomplete"):
                async for _ in client.stream_candles(
                    symbol="EURUSD", timeframe="M1", start_ms=0, end_ms=1
                ):
                    pass
