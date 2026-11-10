import unittest

import httpx
from db_accessor_client import AsyncDatabaseAccessorClient, DatabaseAccessorClient


class ExecutionLogClientTests(unittest.TestCase):
    def test_sync_pagination_and_lightweight_reads(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={})

        with DatabaseAccessorClient() as client:
            client.client = httpx.Client(transport=httpx.MockTransport(respond))
            client.get_backtest_execution_log("run", page=3, page_size=10, include_unexecuted=True)
            client.get_backtest_run("run", include_diagnostics=False)
            client.list_backtest_members("backtest", include_diagnostics=False)
            client.list_backtest_runs(include_diagnostics=False)
        self.assertEqual(requests[0].url.path, "/backtest-runs/run/execution-log")
        self.assertEqual(
            dict(requests[0].url.params), dict(page="3", page_size="10", include_unexecuted="true")
        )
        for request in requests[1:]:
            self.assertEqual(request.url.params["include_diagnostics"], "false")


class AsyncExecutionLogClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_pagination_and_default_compatibility(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={})

        async with AsyncDatabaseAccessorClient() as client:
            client.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            await client.get_backtest_execution_log("run")
            await client.get_backtest_run("run")
            await client.list_backtest_members("backtest", include_diagnostics=False)
        self.assertEqual(
            dict(requests[0].url.params), dict(page="1", page_size="10", include_unexecuted="false")
        )
        self.assertNotIn("include_diagnostics", requests[1].url.params)
        self.assertEqual(requests[2].url.params["include_diagnostics"], "false")
