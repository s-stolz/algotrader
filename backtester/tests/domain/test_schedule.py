import unittest
from typing import Any, cast

from domain.schedule import DAY_MS, MINUTE_MS, DailyTradingSchedule


class TestDailyTradingSchedule(unittest.TestCase):
    def test_boundaries_are_inclusive_start_exclusive_last_entry(self) -> None:
        schedule = DailyTradingSchedule(60, 120, 180)
        for day in (0, DAY_MS):
            self.assertFalse(schedule.allows_entry(day + 60 * MINUTE_MS - 1))
            self.assertTrue(schedule.allows_entry(day + 60 * MINUTE_MS))
            self.assertTrue(schedule.allows_entry(day + 120 * MINUTE_MS - 1))
            self.assertFalse(schedule.allows_entry(day + 120 * MINUTE_MS))
            self.assertEqual(schedule.exit_timestamp(day + 60 * MINUTE_MS), day + 180 * MINUTE_MS)

    def test_invalid_daily_boundaries_are_rejected(self) -> None:
        for values in ((-1, 2, 3), (1, 1, 3), (1, 3, 2), (1, 2, 1440), (True, 2, 3), (1, 2.5, 3)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                DailyTradingSchedule(*cast(Any, values))
        self.assertEqual(DailyTradingSchedule(0, 1, 1).exit_minute_utc, 1)
