import unittest

import numpy as np
from indicator_engine.core.session import SessionWindow


def timestamp(value):
    return int(np.datetime64(value, "ms").astype(np.int64))


class SessionWindowTests(unittest.TestCase):
    def test_utc_bounds_allow_end_at_next_midnight(self):
        bounds = SessionWindow().bounds(timestamp("2026-03-30T12:00"))
        self.assertEqual(bounds.day_start_ms, timestamp("2026-03-30T00:00"))
        self.assertEqual(bounds.start_ms, bounds.day_start_ms)
        self.assertEqual(bounds.end_ms, timestamp("2026-03-31T00:00"))

    def test_calendar_day_duration_changes_at_dst(self):
        bounds = SessionWindow("Europe/London", 540, 600).bounds(timestamp("2026-03-29T12:00"))
        self.assertEqual(bounds.day_end_ms - bounds.day_start_ms, 23 * 3_600_000)
        self.assertEqual(bounds.start_ms, timestamp("2026-03-29T08:00"))

    def test_nonexistent_wall_clock_boundary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            SessionWindow("Europe/London", 90, 180).bounds(timestamp("2026-03-29T12:00"))

    def test_ambiguous_wall_clock_uses_first_occurrence(self):
        bounds = SessionWindow("Europe/London", 90, 180).bounds(timestamp("2026-10-25T12:00"))
        self.assertEqual(bounds.start_ms, timestamp("2026-10-25T00:30"))

    def test_inverted_and_overnight_windows_are_rejected(self):
        for start, end in [(600, 540), (0, 0), (-1, 10), (0, 1441)]:
            with self.assertRaises(ValueError):
                SessionWindow(start_minute=start, end_minute=end)
