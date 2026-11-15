import unittest
from unittest.mock import AsyncMock

from app.history.events import EVENT_STREAM, HistoryEvents

from tests.history.fakes import job


class HistoryEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_invalidation_survives_failed_publication(self):
        redis = AsyncMock()
        redis.xadd.side_effect = [OSError("Redis unavailable"), "1-0"]
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
