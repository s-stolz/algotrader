import unittest

import numpy as np
import pandas as pd
from indicator_engine.adapters.pandas import bars_from_dataframe, result_to_dataframe
from indicator_engine.core.tensor import Tensor


class PandasAdapterTests(unittest.TestCase):
    def test_bars_from_dataframe_single_asset_defaults_asset_id_zero(self) -> None:
        df = pd.DataFrame(
            {"open": [1.0, 2.0], "close": [1.5, 2.5]},
            index=pd.Index([1000, 2000], name="timestamp_ms"),
        )

        bar = bars_from_dataframe(df)

        self.assertEqual(bar.data.shape, (2, 1, 2))
        self.assertTrue(np.array_equal(bar.time, np.array([1000, 2000])))
        self.assertEqual(bar.assets.tolist(), [0])
        self.assertEqual(bar.fields.tolist(), ["open", "close"])
        self.assertAlmostEqual(bar.data[0, 0, 0], 1.0)
        self.assertAlmostEqual(bar.data[1, 0, 1], 2.5)

    def test_bars_from_dataframe_multiindex_preserves_field_asset_values(self) -> None:
        columns = pd.MultiIndex.from_product([["close"], ["EURUSD", "GBPUSD"]])
        df = pd.DataFrame([[1.2, 1.4], [1.3, 1.5]], index=[1000, 2000], columns=columns)

        bar = bars_from_dataframe(df)

        self.assertEqual(bar.data.shape, (2, 2, 1))
        eurusd_idx = list(bar.assets).index("EURUSD")
        gbpusd_idx = list(bar.assets).index("GBPUSD")
        close_idx = list(bar.fields).index("close")
        self.assertAlmostEqual(bar.data[0, eurusd_idx, close_idx], 1.2)
        self.assertAlmostEqual(bar.data[1, gbpusd_idx, close_idx], 1.5)

    def test_result_to_dataframe_expands_param_levels_from_attrs(self) -> None:
        tensor = Tensor(
            data=np.array(
                [
                    [[[1.0, 2.0]], [[3.0, 4.0]]],
                    [[[1.1, 2.1]], [[3.1, 4.1]]],
                ]
            ),
            dims=("time", "asset", "output", "param"),
            coords={
                "time": np.array([1000, 2000], dtype=np.int64),
                "asset": np.array(["EURUSD", "GBPUSD"], dtype=object),
                "output": np.array(["sma"], dtype=object),
                "param": np.array(["window=2", "window=3"], dtype=object),
            },
            attrs={
                "param_names": ["window"],
                "param_values": [{"window": 2}, {"window": 3}],
            },
        )

        df = result_to_dataframe(tensor)

        self.assertIsInstance(df.columns, pd.MultiIndex)
        self.assertEqual(df.columns.names, ["asset", "output", "window"])
        self.assertAlmostEqual(df[("EURUSD", "sma", 2)].iloc[0], 1.0)
        self.assertAlmostEqual(df[("GBPUSD", "sma", 3)].iloc[1], 4.1)


if __name__ == "__main__":
    unittest.main()
