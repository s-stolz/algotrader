from __future__ import annotations

import unittest

from app.api.routers import deals
from app.domain.value_objects import AccountId

from .fakes import FakePositionService


class DealsRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_deal_history(self) -> None:
        response = await deals.get_deal_history(
            fromTs=None,
            toTs=None,
            account_id=AccountId(123),
            service=FakePositionService(),
        )
        self.assertIn("deal_id", response[0])


if __name__ == "__main__":
    unittest.main()
