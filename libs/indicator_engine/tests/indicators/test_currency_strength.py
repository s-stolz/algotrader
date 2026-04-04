import unittest

import numpy as np
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.currency_strength import CurrencyStrength


class CurrencyStrengthTests(unittest.TestCase):
    @staticmethod
    def _required_assets() -> list[str]:
        return [
            "EURUSD",
            "USDJPY",
            "USDCHF",
            "GBPUSD",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
        ]

    def test_currency_strength_raises_when_required_assets_missing(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[1.1]]], dtype=np.float64),
            time=np.array([1000, 2000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(KeyError):
            CurrencyStrength().batch(bar, {})

    def test_currency_strength_constant_prices_are_zero_after_first_row(self) -> None:
        assets = self._required_assets()
        rows = 4
        cols = len(assets)
        data = np.full((rows, cols, 1), 1.0, dtype=np.float64)
        bar = BarTensor(
            data=data,
            time=np.array([1000, 2000, 3000, 4000], dtype=np.int64),
            assets=np.array(assets, dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = CurrencyStrength().batch(bar, {})

        self.assertEqual(out.data.shape, (rows, 1, 8))
        self.assertTrue(np.isnan(out.data[0, 0, :]).all())
        self.assertTrue(np.allclose(out.data[1:, 0, :], 0.0))
        self.assertEqual(out.coords["asset"].tolist(), ["FX"])


if __name__ == "__main__":
    unittest.main()
