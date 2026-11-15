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
