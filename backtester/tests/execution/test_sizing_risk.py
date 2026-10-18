import unittest

from domain.types import ExecutionArrayBundle
from execution.risk import long_only_rule
from execution.sizing import fixed_quantity_sizer


class TestSizingAndRiskTransforms(unittest.TestCase):
    def test_fixed_quantity_sizer_maps_positive_targets(self) -> None:
        bundle = ExecutionArrayBundle(
            timestamp_ms=[1, 2, 3],
            target_quantity_by_symbol={"AAPL": [0.0, 2.0, -1.0]},
        )

        transformed = fixed_quantity_sizer(5.0)(bundle)
        self.assertEqual(transformed.target_quantity_by_symbol["AAPL"], [0.0, 5.0, 0.0])

    def test_fixed_quantity_sizer_rejects_length_mismatch(self) -> None:
        bundle = ExecutionArrayBundle(
            timestamp_ms=[1, 2, 3],
            target_quantity_by_symbol={"AAPL": [1.0, 2.0]},
        )

        with self.assertRaises(ValueError):
            fixed_quantity_sizer(1.0)(bundle)

    def test_long_only_rule_clamps_negatives_and_validates_shape(self) -> None:
        valid = ExecutionArrayBundle(
            timestamp_ms=[1, 2, 3],
            target_quantity_by_symbol={"AAPL": [1.0, -2.0, 0.5]},
        )
        transformed = long_only_rule(valid)
        self.assertEqual(transformed.target_quantity_by_symbol["AAPL"], [1.0, 0.0, 0.5])

        invalid = ExecutionArrayBundle(
            timestamp_ms=[1, 2, 3],
            target_quantity_by_symbol={"AAPL": [1.0, 2.0]},
        )
        with self.assertRaises(ValueError):
            long_only_rule(invalid)


if __name__ == "__main__":
    unittest.main()
