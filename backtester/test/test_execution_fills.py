import unittest

import numpy as np
from domain.enums import GapPolicy, OrderSide
from execution.fills import generate_fills_from_targets


class TestFillGeneration(unittest.TestCase):
    def test_next_bar_open_fill_timing_and_delta(self) -> None:
        fills, executed_delta = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4, 5],
            open_prices=[100.0, 101.0, 102.0, 103.0, 104.0],
            target_quantity=[0.0, 1.0, 1.0, 0.0, 0.0],
            gap_policy=GapPolicy.SKIP,
        )

        self.assertEqual(len(fills), 2)
        self.assertEqual(fills[0].timestamp_ms, 3)
        self.assertEqual(fills[0].side, OrderSide.BUY)
        self.assertEqual(fills[0].quantity, 1.0)
        self.assertEqual(fills[0].price, 102.0)

        self.assertEqual(fills[1].timestamp_ms, 5)
        self.assertEqual(fills[1].side, OrderSide.SELL)
        self.assertEqual(fills[1].quantity, 1.0)
        self.assertEqual(fills[1].price, 104.0)

        np.testing.assert_allclose(executed_delta, np.array([0.0, 0.0, 1.0, 0.0, -1.0]))


if __name__ == "__main__":
    unittest.main()
