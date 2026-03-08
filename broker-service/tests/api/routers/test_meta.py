from __future__ import annotations

import unittest

from app.api.routers import meta

from .fakes import FakeContainer


class MetaRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_shape(self) -> None:
        response = await meta.health(FakeContainer())
        self.assertIn("status", response)
        self.assertIn("components", response)
        self.assertIn("ctrader", response["components"])
        self.assertIn("tokenLifecycle", response["components"])


if __name__ == "__main__":
    unittest.main()
