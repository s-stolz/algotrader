import unittest

import numpy as np
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.bbands import BBANDS


class BBandsTests(unittest.TestCase):
    def test_bbands_simple_values_window_2(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = BBANDS().batch(
            bar,
            {"length": 2, "lower_std": 2.0, "upper_std": 2.0, "source": "close"},
        )
        lower = out.data[:, 0, 0]
        mid = out.data[:, 0, 1]
        upper = out.data[:, 0, 2]

        self.assertTrue(np.isnan(lower[0]))
        self.assertTrue(np.isnan(mid[0]))
        self.assertTrue(np.isnan(upper[0]))

        self.assertAlmostEqual(mid[1], 1.5)
        self.assertAlmostEqual(lower[1], 0.5)
        self.assertAlmostEqual(upper[1], 2.5)

        self.assertAlmostEqual(mid[2], 2.5)
        self.assertAlmostEqual(lower[2], 1.5)
        self.assertAlmostEqual(upper[2], 3.5)

    def test_bbands_raises_for_non_positive_length(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]]], dtype=np.float64),
            time=np.array([1000, 2000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(ValueError):
            BBANDS().batch(
                bar,
                {"length": 0, "lower_std": 2.0, "upper_std": 2.0, "source": "close"},
            )


if __name__ == "__main__":
    unittest.main()
