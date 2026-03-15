import unittest

import numpy as np
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.macd import MACD


class MACDTests(unittest.TestCase):
    def test_macd_constant_series_is_nan_during_warmup_then_zero(self) -> None:
        bar = BarTensor(
            data=np.array([[[10.0]], [[10.0]], [[10.0]], [[10.0]], [[10.0]], [[10.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000, 4000, 5000, 6000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = MACD().batch(bar, {"fast": 2, "slow": 3, "signal": 2, "source": "close"})
        macd = out.data[:, 0, 0]
        signal = out.data[:, 0, 1]
        hist = out.data[:, 0, 2]

        self.assertTrue(np.all(np.isnan(macd[:4])))
        self.assertTrue(np.all(np.isnan(signal[:4])))
        self.assertTrue(np.all(np.isnan(hist[:4])))
        self.assertTrue(np.allclose(macd[4:], 0.0))
        self.assertTrue(np.allclose(signal[4:], 0.0))
        self.assertTrue(np.allclose(hist[4:], 0.0))

    def test_macd_raises_for_unknown_source_field(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(KeyError):
            MACD().batch(bar, {"fast": 2, "slow": 3, "signal": 2, "source": "open"})


if __name__ == "__main__":
    unittest.main()
