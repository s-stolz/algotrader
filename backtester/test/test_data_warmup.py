import unittest

import pandas as pd
from data.warmup import trim_bars_for_execution


class TestWarmupTrimming(unittest.TestCase):
    def test_trim_drops_incomplete_feature_rows_and_applies_window(self) -> None:
        bars = pd.DataFrame(
            {
                "timestamp_ms": [1_000, 2_000, 3_000, 4_000, 5_000],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 10.0, 10.0, 10.0, 10.0],
                "high": [10.0, 10.0, 10.0, 10.0, 10.0],
                "low": [10.0, 10.0, 10.0, 10.0, 10.0],
                "close": [10.0, 10.0, 10.0, 10.0, 10.0],
                "volume": [1.0, 1.0, 1.0, 1.0, 1.0],
                "sma_fast": [None, 1.0, 1.1, 1.2, 1.3],
                "sma_slow": [None, None, 1.0, 1.1, 1.2],
            }
        )

        trimmed = trim_bars_for_execution(
            bars=bars,
            required_features=("sma_fast", "sma_slow"),
            start_ms=2_000,
            end_ms=5_000,
        )

        self.assertEqual(trimmed["timestamp_ms"].tolist(), [3_000, 4_000])
        has_missing = trimmed[["sma_fast", "sma_slow"]].isna().to_numpy().any()
        self.assertFalse(has_missing)

    def test_trim_raises_when_no_rows_remain(self) -> None:
        bars = pd.DataFrame(
            {
                "timestamp_ms": [1_000, 2_000],
                "symbol": ["AAPL", "AAPL"],
                "open": [10.0, 10.0],
                "high": [10.0, 10.0],
                "low": [10.0, 10.0],
                "close": [10.0, 10.0],
                "volume": [1.0, 1.0],
                "sma_fast": [None, None],
                "sma_slow": [None, None],
            }
        )

        with self.assertRaises(ValueError):
            trim_bars_for_execution(
                bars=bars,
                required_features=("sma_fast", "sma_slow"),
                start_ms=1_000,
                end_ms=3_000,
            )


if __name__ == "__main__":
    unittest.main()
