import unittest

from indicator_engine.core.params import ParamGrid


class ParamGridTests(unittest.TestCase):
    def test_param_grid_is_deterministic_and_sorted_by_param_name(self) -> None:
        grid = ParamGrid({"b": [2, 1], "a": [10, 20]})

        self.assertEqual(grid.param_names, ["a", "b"])
        self.assertEqual(
            grid.param_ids,
            [
                "a=10|b=2",
                "a=10|b=1",
                "a=20|b=2",
                "a=20|b=1",
            ],
        )
        self.assertEqual(
            grid.grid_params,
            [
                {"a": 10, "b": 2},
                {"a": 10, "b": 1},
                {"a": 20, "b": 2},
                {"a": 20, "b": 1},
            ],
        )

    def test_set_values_are_normalized_to_sorted_order(self) -> None:
        grid = ParamGrid({"length": {5, 2}})
        self.assertEqual(grid.param_ids, ["length=2", "length=5"])

    def test_empty_grid_produces_default_param(self) -> None:
        grid = ParamGrid({})
        self.assertEqual(len(grid), 1)
        self.assertEqual(grid.param_ids, ["default"])
        self.assertEqual(grid.grid_params, [{}])


if __name__ == "__main__":
    unittest.main()
