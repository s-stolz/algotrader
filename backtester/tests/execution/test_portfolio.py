import unittest

from execution.portfolio import build_equity_curve


class TestPortfolioAccounting(unittest.TestCase):
    def test_build_equity_curve_marks_on_close_with_open_execution_cashflows(self) -> None:
        curve = build_equity_curve(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4, 5],
            close_prices=[100.0, 105.0, 110.0, 108.0, 107.0],
            executed_delta=[0.0, 1.0, 0.0, -1.0, 0.0],
            executed_notional=[0.0, 101.0, 0.0, -108.0, 0.0],
            executed_fees=[0.0, 0.5, 0.0, 0.5, 0.0],
            initial_capital=1_000.0,
        )

        self.assertEqual(len(curve), 5)
        self.assertEqual(curve[1].cash, 898.5)
        self.assertEqual(curve[1].positions["AAPL"], 1.0)
        self.assertEqual(curve[2].equity, 1_008.5)
        self.assertEqual(curve[3].cash, 1_006.0)
        self.assertEqual(curve[4].equity, 1_006.0)


if __name__ == "__main__":
    unittest.main()
