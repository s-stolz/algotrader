from __future__ import annotations

import unittest

from app.api.routers import positions
from app.domain.value_objects import AccountId
from starlette.requests import Request

from .fakes import FakePositionService


class PositionsRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_position_without_body(self) -> None:
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [(b"content-length", b"0")],
                "query_string": b"",
            },
            receive,
        )

        response = await positions.close_position(
            55, request, AccountId(123), FakePositionService()
        )
        self.assertEqual(response["position_id"], 55)


if __name__ == "__main__":
    unittest.main()
