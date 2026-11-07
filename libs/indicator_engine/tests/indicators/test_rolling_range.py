import unittest

import numpy as np
from indicator_engine import get_registry
from indicator_engine.core.bars import BarTensor
from indicator_engine.core.history import HistoryPolicy
from indicator_engine.core.params import ParamGrid
from indicator_engine.engines.update import UpdateEngine
from indicator_engine.indicators.rolling_range import RollingRange


class RollingRangeTests(unittest.TestCase):
    def bars(self, values):
        return BarTensor(
            np.asarray(values, dtype=float)[:, None, :],
            np.arange(len(values)) * 60000,
            np.array(["TEST"]),
            np.array(["high", "low"]),
        )

    def test_trailing_window_warmup_nan_and_eviction(self):
        bars = self.bars([[9, 1], [7, 3], [8, 2], [6, 4], [float("nan"), 0], [5, 2], [4, 3]])
        actual = RollingRange().batch(bars, {"window": 2}).data[:, 0]
        np.testing.assert_allclose(
            actual,
            [[np.nan, np.nan], [9, 1], [8, 2], [8, 2], [np.nan, 0], [np.nan, 0], [5, 2]],
            equal_nan=True,
        )
        np.testing.assert_allclose(
            RollingRange().batch(bars, {"window": 1}).data[:, 0], bars.data[:, 0], equal_nan=True
        )
        self.assertTrue(np.isnan(RollingRange().batch(bars, {"window": 10}).data).all())

    def test_live_revisions_and_new_candles_match_batch(self):
        engine = UpdateEngine(get_registry(), HistoryPolicy(mode="rolling", max_rows=3))
        engine.register_indicator(
            "rolling_range", "M1", ["TEST"], ["high", "low"], ParamGrid({"window": 3})
        )
        rows = []
        for timestamp, row in [
            (0, [9, 1]),
            (1, [7, 3]),
            (2, [8, 2]),
            (2, [10, 0]),
            (3, [6, 4]),
            (4, [5, 3]),
            (5, [4, 2]),
        ]:
            if timestamp == len(rows):
                rows.append(row)
            else:
                rows[timestamp] = row
            live = engine.on_bar("M1", timestamp * 60000, np.array([row], dtype=float))[
                "rolling_range"
            ]
            batch = RollingRange().batch(self.bars(rows), {"window": 3})
            np.testing.assert_allclose(live.data[0, :, :, 0], batch.data[-1], equal_nan=True)

    def test_invalid_windows(self):
        for window in (0, -1, 1.5, True, 5001):
            with self.subTest(window=window), self.assertRaises(ValueError):
                RollingRange().batch(self.bars([[2, 1]]), {"window": window})
