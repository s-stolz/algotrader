import json
import unittest
from unittest.mock import AsyncMock

from app.history.events import EVENT_STREAM, HistoryEvents

from tests.history.fakes import job


class HistoryEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_invalidation_survives_failed_publication(self):
        redis = AsyncMock()
        redis.xadd.side_effect = [OSError("Redis unavailable"), "1-0", "2-0"]
        events = HistoryEvents(redis)
        value = job()
        value.update(status="completed", revision=5)
        events.changed(value)
        await events.flush()
        self.assertIn(value["id"], events.pending)
        await events.flush()
        self.assertFalse(events.pending)
        self.assertEqual(redis.xadd.call_args.args[0], EVENT_STREAM)
        self.assertIn('"revision": 5', redis.xadd.call_args.args[1]["event"])

    async def test_restart_resnapshot_does_not_depend_on_recent_job_enumeration(self):
        redis = AsyncMock()
        redis.xadd.side_effect = [OSError("Redis unavailable"), "1-0"]
        events = HistoryEvents(redis)
        self.assertFalse(events.pending)
        await events.flush()
        self.assertTrue(events.resnapshot_pending)
        await events.flush()
        self.assertFalse(events.resnapshot_pending)
        self.assertIn("historyDownloadsResnapshot", redis.xadd.call_args.args[1]["event"])

    async def test_job_publication_failure_requires_a_new_global_resnapshot(self):
        redis = AsyncMock()
        redis.xadd.side_effect = ["1-0", OSError("interrupted"), "2-0", "3-0"]
        events = HistoryEvents(redis)
        value = job()
        value.update(status="completed", revision=8)
        events.changed(value)
        await events.flush()
        self.assertTrue(events.resnapshot_pending)
        self.assertIn(value["id"], events.pending)
        await events.flush()
        kinds = [json.loads(call.args[1]["event"])["type"] for call in redis.xadd.call_args_list]
        self.assertEqual(
            kinds,
            [
                "historyDownloadsResnapshot",
                "historyDownloadChanged",
                "historyDownloadsResnapshot",
                "historyDownloadChanged",
            ],
        )
        self.assertFalse(events.pending)
