"""Both transports preserve conditional pending-recovery identity."""

import json
import unittest

import httpx
from db_accessor_client import AsyncDatabaseAccessorClient, DatabaseAccessorClient

PENDING = dict(
    symbol_id=1,
    account_id="account",
    recovery_id="identity",
    revision=2,
    next_ms=60000,
    target_ms=179999,
    trigger="startup",
)


GUARD = dict(symbol_id=1, account_id="account", write_id="batch", boundary_ms=60000)


def handler(request):
    if "/live-writes/" in request.url.path:
        if request.method == "GET":
            assert request.url.params["account_id"] == "account"
            return httpx.Response(200, json={"guard": GUARD})
        data = json.loads(request.content)
        if request.url.path.endswith("/begin"):
            assert data == dict(symbol_id=1, account_id="account", boundary_ms=60000)
            return httpx.Response(200, json=GUARD)
        assert data == dict(symbol_id=1, account_id="account", write_id="batch")
        return httpx.Response(200, json={"updated": False})
    if request.method == "GET":
        assert request.url.params["account_id"] == "account"
        return httpx.Response(200, json={"pending": PENDING})
    data = json.loads(request.content)
    if request.url.path == "/recoveries/begin":
        assert data == dict(
            symbol_id=1, account_id="account", start_ms=60000, target_ms=179999, trigger="startup"
        )
        return httpx.Response(200, json=PENDING)
    assert data == dict(
        symbol_id=1,
        account_id="account",
        recovery_id="identity",
        revision=2,
        expected_start_ms=60000,
        next_ms=180000,
    )
    return httpx.Response(200, json={"updated": False})


class RecoveryClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_and_async_preserve_revision_and_conditional_result(self):
        with DatabaseAccessorClient() as client:
            client.client.close()
            client.client = httpx.Client(transport=httpx.MockTransport(handler))
            self.assertEqual(client.get_live_write_guard(1, "account"), GUARD)
            self.assertEqual(client.begin_live_write(1, "account", 60000), GUARD)
            self.assertFalse(client.finish_live_write(GUARD))
            self.assertEqual(client.get_pending_recovery(1, "account"), PENDING)
            self.assertEqual(client.begin_recovery(1, "account", 60000, 179999, "startup"), PENDING)
            self.assertFalse(client.advance_recovery(PENDING, 180000))
        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            self.assertEqual(await client.get_live_write_guard(1, "account"), GUARD)
            self.assertEqual(await client.begin_live_write(1, "account", 60000), GUARD)
            self.assertFalse(await client.finish_live_write(GUARD))
            self.assertEqual(await client.get_pending_recovery(1, "account"), PENDING)
            self.assertEqual(
                await client.begin_recovery(1, "account", 60000, 179999, "startup"), PENDING
            )
            self.assertFalse(await client.advance_recovery(PENDING, 180000))
