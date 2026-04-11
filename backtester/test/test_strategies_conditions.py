import unittest

import numpy as np
from strategies.conditions import above, below, crossover, crossunder


class TestConditionHelpers(unittest.TestCase):
    def test_crossover_detects_upward_cross(self) -> None:
        left = np.array([1.0, 2.0, 3.0, 2.0])
        right = np.array([2.0, 2.0, 2.0, 2.0])

        mask = crossover(left, right)

        self.assertEqual(mask.tolist(), [False, False, True, False])

    def test_crossunder_detects_downward_cross(self) -> None:
        left = np.array([3.0, 2.0, 1.0, 2.0])
        right = np.array([2.0, 2.0, 2.0, 2.0])

        mask = crossunder(left, right)

        self.assertEqual(mask.tolist(), [False, False, True, False])

    def test_nan_history_prevents_false_cross(self) -> None:
        left = np.array([np.nan, 3.0, 3.0])
        right = np.array([np.nan, 2.0, 2.0])

        mask = crossover(left, right)

        self.assertEqual(mask.tolist(), [False, False, False])

    def test_above_array_like(self) -> None:
        left = np.array([0.0, 1.0, 4.0, 8.0])
        right = np.array([1.0, 2.0, 3.0, 4.0])

        mask = above(left, right)

        self.assertEqual(mask.tolist(), [False, False, True, True])

    def test_below_array_like(self) -> None:
        left = np.array([0.0, 1.0, 4.0, 8.0])
        right = np.array([1.0, 2.0, 3.0, 4.0])

        mask = below(left, right)

        self.assertEqual(mask.tolist(), [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
