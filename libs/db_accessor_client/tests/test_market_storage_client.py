import json
import unittest

import httpx
from db_accessor_client import AsyncDatabaseAccessorClient, DatabaseAccessorClient


class MarketStorageClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_transports_resolve_stable_market_identity_and_coverage(self):
        paths = []

        def handler(request):
            paths.append(request.url.path)
            return httpx.Response(200, json={"market_id": 12})

        with DatabaseAccessorClient() as client:
            client.client.close()
            client.client = httpx.Client(transport=httpx.MockTransport(handler))
            self.assertEqual(client.get_market_by_id(12), {"market_id": 12})
            self.assertEqual(client.get_market_coverage(12), {"market_id": 12})
        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            self.assertEqual(await client.get_market_by_id(12), {"market_id": 12})
            self.assertEqual(await client.get_market_coverage(12), {"market_id": 12})
        self.assertEqual(paths, ["/markets/id/12", "/markets/id/12/coverage"] * 2)

    async def test_both_write_transports_preserve_optional_market_id(self):
        requests = []

        def handler(request):
            requests.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"status": "ok"})

        with DatabaseAccessorClient() as client:
            client.client.close()
            client.client = httpx.Client(transport=httpx.MockTransport(handler))
            client.insert_candles("EURUSD", [], exchange="FX", market_id=12)
            client.write_historical_candles("EURUSD", [], 0, 59999, exchange="FX", market_id=12)
            client.insert_candles("EURUSD", [])
        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            await client.insert_candles("EURUSD", [], exchange="FX", market_id=12)
            await client.write_historical_candles(
                "EURUSD", [], 0, 59999, exchange="FX", market_id=12
            )
            await client.insert_candles("EURUSD", [])
        self.assertEqual(requests[:3], requests[3:])
        self.assertEqual(requests[0][1]["market_id"], 12)
        self.assertEqual(requests[1][1]["market_id"], 12)
        self.assertNotIn("market_id", requests[2][1])
