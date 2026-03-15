import unittest

import numpy as np
import pandas as pd

from indicator_engine import list_indicators, run, run_batch


class DefaultsTests(unittest.TestCase):
    def test_run_sma_returns_expected_values(self) -> None:
        df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0, 4.0]},
            index=pd.Index([1000, 2000, 3000, 4000], name="timestamp_ms"),
        )

        out = run("sma", df, params={"window": 2, "source": "close"})

        self.assertEqual(list(out.columns), ["sma"])
        self.assertTrue(np.isnan(out["sma"].iloc[0]))
        self.assertAlmostEqual(out["sma"].iloc[1], 1.5)
        self.assertAlmostEqual(out["sma"].iloc[3], 3.5)

    def test_run_batch_dict_of_dataframes_requires_timeframe(self) -> None:
        df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0]},
            index=pd.Index([1000, 2000, 3000], name="timestamp_ms"),
        )
        bundle = {"M1": df}

        with self.assertRaises(ValueError):
            run_batch("sma", bundle, params={"window": 2})

    def test_run_batch_dict_of_dataframes_with_timeframe(self) -> None:
        df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0]},
            index=pd.Index([1000, 2000, 3000], name="timestamp_ms"),
        )
        bundle = {"M1": df}

        result = run_batch("sma", bundle, params={"window": 2}, timeframe="M1")
        tensor = result.tensor

        self.assertEqual(tensor.dims, ("time", "asset", "output", "param"))
        self.assertEqual(tensor.data.shape, (3, 1, 1, 1))
        self.assertEqual(list(tensor.coords["output"]), ["sma"])
        self.assertEqual(list(tensor.coords["param"]), ["window=2"])

    def test_list_indicators_contains_expected_defaults(self) -> None:
        ids = {item["id"] for item in list_indicators()}
        self.assertIn("sma", ids)
        self.assertIn("rsi", ids)
        self.assertIn("macd", ids)
        self.assertIn("bbands", ids)
        self.assertIn("currency_strength", ids)


if __name__ == "__main__":
    unittest.main()
