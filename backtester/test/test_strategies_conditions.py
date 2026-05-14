import unittest

import numpy as np
from strategies.conditions import ConditionRule, above, below, crossover, crossunder


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

    def test_condition_rule_evaluates_crossover_vectorized_and_sequentially(self) -> None:
        rule = ConditionRule.crossover("sma_fast", "sma_slow")
        feature_map = {
            "sma_fast": [1.0, 2.0, 3.0, 2.0],
            "sma_slow": [2.0, 2.0, 2.0, 2.0],
        }

        mask = rule.evaluate_vectorized(feature_map)
        crossed = rule.evaluate_sequential(
            previous={"sma_fast": 2.0, "sma_slow": 2.0},
            current={"sma_fast": 3.0, "sma_slow": 2.0},
        )
        first_bar_crossed = rule.evaluate_sequential(
            previous=None,
            current={"sma_fast": 3.0, "sma_slow": 2.0},
        )

        self.assertEqual(mask.tolist(), [False, False, True, False])
        self.assertTrue(crossed)
        self.assertFalse(first_bar_crossed)

    def test_condition_rule_evaluates_crossunder_vectorized_and_sequentially(self) -> None:
        rule = ConditionRule.crossunder("sma_fast", "sma_slow")
        feature_map = {
            "sma_fast": [3.0, 2.0, 1.0, 2.0],
            "sma_slow": [2.0, 2.0, 2.0, 2.0],
        }

        mask = rule.evaluate_vectorized(feature_map)
        crossed = rule.evaluate_sequential(
            previous={"sma_fast": 2.0, "sma_slow": 2.0},
            current={"sma_fast": 1.0, "sma_slow": 2.0},
        )

        self.assertEqual(mask.tolist(), [False, False, True, False])
        self.assertTrue(crossed)

    def test_condition_rule_evaluates_above_and_below_sequentially(self) -> None:
        above_rule = ConditionRule.above("fast", "slow")
        below_rule = ConditionRule.below("fast", "slow")

        current = {"fast": 3.0, "slow": 2.0}
        feature_map = {
            "fast": [1.0, 3.0],
            "slow": [2.0, 2.0],
        }

        self.assertEqual(above_rule.evaluate_vectorized(feature_map).tolist(), [False, True])
        self.assertEqual(below_rule.evaluate_vectorized(feature_map).tolist(), [True, False])
        self.assertTrue(above_rule.evaluate_sequential(previous=None, current=current))
        self.assertFalse(below_rule.evaluate_sequential(previous=None, current=current))

    def test_condition_rule_rejects_missing_features(self) -> None:
        rule = ConditionRule.above("fast", "slow")

        with self.assertRaisesRegex(ValueError, "missing required feature"):
            rule.evaluate_vectorized({"fast": [1.0, 2.0]})

        with self.assertRaisesRegex(ValueError, "missing required feature"):
            rule.evaluate_sequential(previous=None, current={"fast": 2.0})


if __name__ == "__main__":
    unittest.main()
