import json
import unittest

import httpx
from db_accessor_client import AsyncDatabaseAccessorClient, DatabaseAccessorClient
from db_accessor_client.errors import DatabaseAccessorClientError


class HistoryDownloadClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_transports_preserve_fencing_and_nullable_claim_results(self):
        requests = []
        job = {"id": "job1", "revision": 8, "status": "downloading"}
        page = dict(
            owner_token="worker",
            revision=8,
            expected_cursor_ms=120000,
            next_cursor_ms=60000,
            fetched_count=0,
            candles=[],
        )

        def handler(request):
            requests.append(
                (request.url.path, json.loads(request.content) if request.content else None)
            )
            if request.url.path.endswith("/claim"):
                return httpx.Response(200, content="null")
            if request.url.path.endswith("/retry"):
                return httpx.Response(409, json={"detail": "another active job"})
            return httpx.Response(200, json=job)

        with DatabaseAccessorClient() as client:
            client.client.close()
            client.client = httpx.Client(transport=httpx.MockTransport(handler))
            self.assertIsNone(client.claim_history_download_job("job1", "worker"))
            self.assertEqual(client.commit_history_download_page("job1", page), job)
            self.assertEqual(client.cancel_history_download_job("job1"), job)
            with self.assertRaises(DatabaseAccessorClientError) as raised:
                client.retry_history_download_job("job1")
            self.assertEqual(raised.exception.status_code, 409)
        async with AsyncDatabaseAccessorClient() as client:
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            self.assertIsNone(await client.claim_history_download_job("job1", "worker"))
            self.assertEqual(await client.commit_history_download_page("job1", page), job)
            self.assertEqual(await client.cancel_history_download_job("job1"), job)
            with self.assertRaises(DatabaseAccessorClientError) as raised:
                await client.retry_history_download_job("job1")
            self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(requests[:4], requests[4:])
        self.assertEqual(requests[1], ("/history-download-jobs/job1/pages", page))
