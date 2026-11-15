import unittest

import httpx
from app.broker_client import BrokerClient


class BrokerIdentityRequestsTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_and_stop_carry_frozen_instrument_id(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={})

        client = BrokerClient("http://broker", "123")
        await client.client.aclose()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            await client.start_trendbar_stream("EURUSD", "M1", expected_symbol_id=17)
            await client.stop_trendbar_stream("EURUSD", "M1", expected_symbol_id=17)
        finally:
            await client.close()
        self.assertEqual(
            [request.url.params["expected_symbol_id"] for request in requests], ["17", "17"]
        )
        self.assertEqual([request.headers["X-Account-Id"] for request in requests], ["123", "123"])
