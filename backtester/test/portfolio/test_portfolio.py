import os
import sys
import unittest

import pandas as pd
import pandas.testing as pdt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.portfolio import Portfolio


class TestPortfolio(unittest.TestCase):
    def test_signals_to_positions_ffill_and_bool(self) -> None:
        index = pd.date_range("2026-01-01", periods=4, freq="min", tz="UTC")
        buy_signals = pd.DataFrame({"open": [False, True, False, False]}, index=index)
        sell_signals = pd.DataFrame({"open": [False, False, False, True]}, index=index)

        positions = Portfolio.signals_to_positions(buy_signals, sell_signals)
        expected = pd.DataFrame({"open": [False, True, True, False]}, index=index, dtype=bool)

        pdt.assert_frame_equal(positions, expected)

    def test_from_signals_aligns_columns_and_produces_returns(self) -> None:
        index = pd.date_range("2026-01-01", periods=5, freq="min", tz="UTC")
        data = pd.DataFrame({"open": [100.0, 110.0, 121.0, 133.1, 146.41]}, index=index)

        buy_signals = pd.DataFrame({"sma_fast": [True, False, False, False, False]}, index=index)
        sell_signals = pd.DataFrame({"sma_fast": [False, False, False, False, False]}, index=index)

        portfolio = Portfolio.from_signals(data, buy_signals, sell_signals)

        self.assertEqual(list(portfolio.positions.columns), ["open"])
        self.assertEqual(list(portfolio.strat_rets.columns), ["open"])
        self.assertGreater(portfolio.strat_rets["open"].sum(), 0.0)

    def test_stats_are_non_zero_for_profitable_series(self) -> None:
        index = pd.date_range("2026-01-01", periods=5, freq="min", tz="UTC")
        data = pd.DataFrame({"open": [100.0, 110.0, 121.0, 133.1, 146.41]}, index=index)

        buy_signals = pd.DataFrame({"open": [True, False, False, False, False]}, index=index)
        sell_signals = pd.DataFrame({"open": [False, False, False, False, False]}, index=index)

        portfolio = Portfolio.from_signals(data, buy_signals, sell_signals)
        stats = portfolio.get_stats()

        self.assertIn("Profit (%)", stats.columns)
        self.assertIn("Profit ($)", stats.columns)
        self.assertGreater(float(stats.loc["open", "Profit (%)"]), 0.0)
        self.assertGreater(float(stats.loc["open", "Profit ($)"]), 0.0)


if __name__ == "__main__":
    unittest.main()
