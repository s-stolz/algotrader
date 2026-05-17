from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain.models import Trendbar
from app.domain.value_objects import Timeframe
from app.infrastructure.ctrader_client import (
    _filter_trendbars_by_time_range,
    _trendbar_chunk_to,
    _trendbar_count_for_range,
)


class TrendbarRangeTests(unittest.TestCase):
    def test_count_for_range_uses_requested_time_bucket_count(self) -> None:
        start = 1_000_000
        end = start + (50 * 60_000)

        count = _trendbar_count_for_range(Timeframe.M1, start, end, max_count=10_000)

        self.assertEqual(count, 51)

    def test_count_for_range_caps_at_chunk_size(self) -> None:
        start = 1_000_000
        end = start + (20_000 * 60_000)

        count = _trendbar_count_for_range(Timeframe.M1, start, end, max_count=10_000)

        self.assertEqual(count, 10_000)

    def test_chunk_to_spans_exactly_chunk_size_bars(self) -> None:
        start = 1_000_000

        chunk_to = _trendbar_chunk_to(
            Timeframe.M1,
            from_ts=start,
            chunk_size=10_000,
            final_to=None,
        )

        self.assertEqual(chunk_to, start + (9_999 * 60_000))

    def test_chunk_to_is_capped_by_final_to(self) -> None:
        start = 1_000_000
        final_to = start + (50 * 60_000)

        chunk_to = _trendbar_chunk_to(
            Timeframe.M1,
            from_ts=start,
            chunk_size=10_000,
            final_to=final_to,
        )

        self.assertEqual(chunk_to, final_to)

    def test_filter_removes_ctrader_bars_outside_requested_range(self) -> None:
        start = 1_000_000
        end = start + (2 * 60_000)
        bars = [
            self._bar(start - 60_000),
            self._bar(start),
            self._bar(start + 60_000),
            self._bar(end),
            self._bar(end + 60_000),
        ]

        filtered = _filter_trendbars_by_time_range(bars, start, end)

        self.assertEqual([bar.t for bar in filtered], [start, start + 60_000, end])

    @staticmethod
    def _bar(timestamp_ms: int) -> Trendbar:
        return Trendbar(
            o=Decimal("1.0"),
            h=Decimal("1.0"),
            l=Decimal("1.0"),
            c=Decimal("1.0"),
            v=1,
            t=timestamp_ms,
        )


if __name__ == "__main__":
    unittest.main()
