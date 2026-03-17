import unittest

import numpy as np
from indicator_engine.core.tensor import Tensor


class TensorTests(unittest.TestCase):
    def test_latest_removes_requested_dimension(self) -> None:
        tensor = Tensor(
            data=np.arange(12, dtype=np.float64).reshape(3, 2, 2),
            dims=("time", "asset", "output"),
            coords={
                "time": np.array([1000, 2000, 3000], dtype=np.int64),
                "asset": np.array(["EURUSD", "USDJPY"], dtype=object),
                "output": np.array(["value", "signal"], dtype=object),
            },
        )

        latest = tensor.latest()

        self.assertEqual(latest.dims, ("asset", "output"))
        self.assertEqual(latest.data.shape, (2, 2))
        self.assertNotIn("time", latest.coords)
        np.testing.assert_array_equal(latest.data, tensor.data[-1])

    def test_scalar_requires_singleton_tensor(self) -> None:
        tensor = Tensor(
            data=np.array([[[[42.5]]]], dtype=np.float64),
            dims=("time", "asset", "output", "param"),
            coords={},
        )
        self.assertEqual(tensor.scalar(), 42.5)

        non_scalar = Tensor(data=np.array([1.0, 2.0]), dims=("time",), coords={})
        with self.assertRaises(ValueError):
            non_scalar.scalar()

    def test_latest_value_singleton_tensor(self) -> None:
        tensor = Tensor(
            data=np.array([[[[101.25]]]], dtype=np.float64),
            dims=("time", "asset", "output", "param"),
            coords={
                "time": np.array([1710000000000], dtype=np.int64),
                "asset": np.array(["EURUSD"], dtype=object),
                "output": np.array(["value"], dtype=object),
                "param": np.array(["window=20"], dtype=object),
            },
        )

        self.assertEqual(tensor.latest_value(), 101.25)

    def test_latest_value_requires_selector_for_multi_dim(self) -> None:
        tensor = Tensor(
            data=np.array(
                [
                    [
                        [[1.0], [2.0]],
                        [[3.0], [4.0]],
                    ]
                ],
                dtype=np.float64,
            ),
            dims=("time", "asset", "output", "param"),
            coords={
                "time": np.array([1], dtype=np.int64),
                "asset": np.array(["EURUSD", "USDJPY"], dtype=object),
                "output": np.array(["value", "signal"], dtype=object),
                "param": np.array(["default"], dtype=object),
            },
        )

        with self.assertRaises(ValueError):
            tensor.latest_value()

        self.assertEqual(
            tensor.latest_value(asset="USDJPY", output="signal", param="default"),
            4.0,
        )


if __name__ == "__main__":
    unittest.main()
