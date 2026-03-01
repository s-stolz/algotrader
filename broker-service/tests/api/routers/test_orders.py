from __future__ import annotations

import json
import unittest

from app.api.routers import orders
from app.domain.value_objects import AccountId

from .fakes import FakeOrderService


def _request_with_json(payload: dict):
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "query_string": b"",
    }
    return Request(scope, receive)


class OrdersRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_place_order(self) -> None:
        request = _request_with_json(
            {
                "symbol": "EURUSD",
                "orderType": "MARKET",
                "tradeSide": "BUY",
                "volume": 100,
            }
        )
        response = await orders.place_order(request, AccountId(123), FakeOrderService())
        self.assertEqual(response["status"], "accepted")

    async def test_get_open_orders(self) -> None:
        response = await orders.get_open_orders(AccountId(123), FakeOrderService())
        self.assertEqual(response[0]["order_type"], "MARKET")


if __name__ == "__main__":
    unittest.main()
