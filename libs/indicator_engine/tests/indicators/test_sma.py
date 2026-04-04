import unittest

import numpy as np
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.sma import SMA


class SMATests(unittest.TestCase):
    def test_sma_simple_values_window_2(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]], [[4.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000, 4000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = SMA().batch(bar, {"window": 2, "source": "close"})

        values = out.data[:, 0, 0]
        self.assertTrue(np.isnan(values[0]))
        self.assertAlmostEqual(values[1], 1.5)
        self.assertAlmostEqual(values[2], 2.5)
        self.assertAlmostEqual(values[3], 3.5)

    def test_sma_raises_for_unknown_source_field(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]]], dtype=np.float64),
            time=np.array([1000, 2000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(KeyError):
            SMA().batch(bar, {"window": 2, "source": "open"})

    def test_sma_raises_for_non_positive_window(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]]], dtype=np.float64),
            time=np.array([1000, 2000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(ValueError):
            SMA().batch(bar, {"window": 0, "source": "close"})


if __name__ == "__main__":
    unittest.main()
