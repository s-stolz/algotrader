from __future__ import annotations

import json
import unittest

from app.api.validation import parse_order_request, read_json_body
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request


def _request_with_json(payload: dict) -> Request:
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

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


class ValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_order_request_valid(self) -> None:
        payload = parse_order_request(
            {
                "symbol": "EURUSD",
                "orderType": "MARKET",
                "tradeSide": "BUY",
                "volume": 100,
            }
        )
        self.assertEqual(payload["orderType"], "MARKET")

    async def test_parse_order_request_missing_required(self) -> None:
        with self.assertRaises(RequestValidationError) as ctx:
            parse_order_request(
                {
                    "orderType": "MARKET",
                    "tradeSide": "BUY",
                    "volume": 100,
                }
            )
        self.assertEqual(ctx.exception.errors()[0]["loc"], ["body", "symbol"])

    async def test_read_json_body(self) -> None:
        request = _request_with_json({"symbol": "EURUSD"})
        body = await read_json_body(request)
        self.assertEqual(body["symbol"], "EURUSD")


if __name__ == "__main__":
    unittest.main()
