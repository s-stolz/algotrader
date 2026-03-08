from __future__ import annotations

import unittest

from app.api.routers import accounts

from .fakes import FakeAccountService


class AccountsRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_accounts(self) -> None:
        response = await accounts.list_accounts(FakeAccountService())
        self.assertIn("account_id", response[0])


if __name__ == "__main__":
    unittest.main()
