import unittest

from execution.portfolio import build_equity_curve


class TestPortfolioAccounting(unittest.TestCase):
    def test_build_equity_curve_updates_cash_positions_and_equity(self) -> None:
        curve = build_equity_curve(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4, 5],
            open_prices=[100.0, 101.0, 102.0, 103.0, 104.0],
            executed_delta=[0.0, 1.0, 0.0, -1.0, 0.0],
            initial_capital=1_000.0,
        )

        self.assertEqual(len(curve), 5)
        self.assertEqual(curve[1].cash, 899.0)
        self.assertEqual(curve[1].positions["AAPL"], 1.0)
        self.assertEqual(curve[2].equity, 1_001.0)
        self.assertEqual(curve[3].cash, 1_002.0)
        self.assertEqual(curve[4].equity, 1_002.0)


if __name__ == "__main__":
    unittest.main()
