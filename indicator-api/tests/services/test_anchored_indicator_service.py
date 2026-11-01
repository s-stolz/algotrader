import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from app.services.anchored_indicator_service import calculate_anchored_indicator


class OpeningRangeHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_after_cutoff_request_loads_formation_without_requiring_earlier_candles(self):
        await self._check_window("UTC", "2026-01-05T09:30", "2026-01-05T00:00")

    async def test_named_timezone_history_uses_local_midnight(self):
        await self._check_window("America/New_York", "2026-01-05T14:30", "2026-01-05T05:00")

    async def _check_window(self, zone, formation_start, midnight):
        start = int(np.datetime64(formation_start, "ms").astype(np.int64))
        step = 300_000
        times = start + np.arange(8) * step
        candles = pd.DataFrame(
            {"high": [11, 12, 13, 12, 14, 13, 100, 200], "low": [5, 4, 6, 3, 2, 5, -10, -20]},
            index=pd.to_datetime(times, unit="ms", utc=True),
        )
        calls = []

        async def fetch(**kwargs):
            calls.append(kwargs)
            result = candles
            if kwargs["start_ms"] is not None:
                result = result.loc[
                    result.index >= pd.to_datetime(kwargs["start_ms"], unit="ms", utc=True)
                ]
            if kwargs["end_ms"] is not None:
                result = result.loc[
                    result.index < pd.to_datetime(kwargs["end_ms"], unit="ms", utc=True)
                ]
            return result.tail(kwargs["limit"]) if kwargs["limit"] is not None else result

        with patch("app.services.anchored_indicator_service.get_candles", side_effect=fetch):
            result = await calculate_anchored_indicator(
                engine_id="opening_range",
                symbol="TEST",
                exchange=None,
                timeframe="M5",
                start_ms=start + 6 * step,
                end_ms=start + 8 * step,
                limit=None,
                parameters={
                    "start_time": "09:30",
                    "end_time": "10:00",
                    "extension_end_time": "11:00",
                    "timezone": zone,
                },
            )
        self.assertEqual(result.range_high.tolist(), [14, 14])
        self.assertEqual(result.range_low.tolist(), [2, 2])
        self.assertEqual(result.ready.tolist(), [1, 1])
        self.assertEqual(result.range_start_ms.tolist(), [start, start])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["start_ms"], int(np.datetime64(midnight, "ms").astype(np.int64)))
