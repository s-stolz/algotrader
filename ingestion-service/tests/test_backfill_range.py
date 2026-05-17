from __future__ import annotations

import unittest

from main import IngestionService


class BackfillRangeTests(unittest.TestCase):
    def test_next_candle_ts_advances_by_timeframe(self) -> None:
        latest_ts = 1_778_878_560_000

        next_ts = IngestionService._next_candle_ts_ms(latest_ts, timeframe_minutes=1)

        self.assertEqual(next_ts, latest_ts + 60_000)


if __name__ == "__main__":
    unittest.main()
