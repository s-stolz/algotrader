import unittest

import numpy as np
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.rsi import RSI


class RSITests(unittest.TestCase):
    def test_rsi_increasing_series_hits_100_after_warmup(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]], [[4.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000, 4000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = RSI().batch(bar, {"length": 2, "source": "close"})
        values = out.data[:, 0, 0]

        self.assertTrue(np.isnan(values[0]))
        self.assertTrue(np.isnan(values[1]))
        self.assertAlmostEqual(values[2], 100.0)
        self.assertAlmostEqual(values[3], 100.0)

    def test_rsi_returns_all_nan_when_not_enough_history(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = RSI().batch(bar, {"length": 3, "source": "close"})
        self.assertTrue(np.isnan(out.data[:, 0, 0]).all())

    def test_rsi_raises_for_non_positive_length(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(ValueError):
            RSI().batch(bar, {"length": 0, "source": "close"})


if __name__ == "__main__":
    unittest.main()
