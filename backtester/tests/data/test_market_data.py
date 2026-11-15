import unittest

import numpy as np
import pandas as pd
from data.market_data import load_market_data, load_raw_market_data
from data.normalization import normalize_bar_data
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class _FakeHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        _ = kwargs
        return self._bars.copy()


class TestMarketDataPipeline(unittest.TestCase):
    def test_warmup_recovery_counts_normalized_candles_and_continues_past_invalid_history(
        self,
    ) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        offsets = [-4, -3, -1, -1, 0, 1, 2]
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + offset * minute for offset in offsets],
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": [10.0, np.nan, 10.0, 10.0, 10.0, 10.0, 10.0],
                "volume": 1000.0,
            }
        )
        calls = []

        class Adapter:
            def fetch_bars(self, **kwargs):
                calls.append(kwargs)
                frame = bars.loc[bars.timestamp_ms < kwargs["end_ms"]]
                if kwargs["start_ms"] is not None:
                    frame = frame.loc[frame.timestamp_ms >= kwargs["start_ms"]]
                limit = kwargs.get("limit")
                return frame.tail(limit).copy() if limit is not None else frame.copy()

        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="M1",
            start_ms=start_ms,
            end_ms=start_ms + 2 * minute,
            strategy=StrategyConfig("sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )
        normalized = load_raw_market_data(
            request=request,
            strategy=build_sma_crossover_strategy(fast_window=2, slow_window=3),
            data_adapter=Adapter(),
        )

        self.assertEqual(
            normalized.timestamp_ms.tolist(),
            [start_ms + offset * minute for offset in [-4, -1, 0, 1]],
        )
        self.assertEqual(len(calls), 3)
        self.assertEqual([call["limit"] for call in calls[1:]], [1, 1])
        self.assertEqual(
            [call["end_ms"] for call in calls[1:]],
            [start_ms - 2 * minute, start_ms - 3 * minute],
        )

    def test_load_market_data_normalizes_indicators_and_trimming(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="M1",
            start_ms=start_ms,
            end_ms=start_ms + (5 * minute),
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        raw_bars = pd.DataFrame(
            {
                "timestamp_ms": [
                    start_ms + (4 * minute),
                    start_ms - (2 * minute),
                    start_ms + minute,
                    start_ms - minute,
                    start_ms + (3 * minute),
                    start_ms + (2 * minute),
                    start_ms,
                ],
                "symbol": ["AAPL"] * 7,
                "open": ["14", "8", "11", "9", "13", "12", "10"],
                "high": ["14.5", "8.5", "11.5", "9.5", "13.5", "12.5", "10.5"],
                "low": ["13.5", "7.5", "10.5", "8.5", "12.5", "11.5", "9.5"],
                "close": ["14", "8", "11", "9", "13", "12", "10"],
                "volume": ["1000", "1000", "1000", "1000", "1000", "1000", "1000"],
            }
        )
        adapter = _FakeHistoricalAdapter(raw_bars)

        prepared = load_market_data(
            request=request,
            strategy=strategy,
            data_adapter=adapter,
        )

        timestamps = prepared["timestamp_ms"].tolist()
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue((prepared["timestamp_ms"] >= request.start_ms).all())
        self.assertTrue((prepared["timestamp_ms"] < request.end_ms).all())
        self.assertIn("sma_fast", prepared.columns)
        self.assertIn("sma_slow", prepared.columns)
        has_missing = prepared[["sma_fast", "sma_slow"]].isna().to_numpy().any()
        self.assertFalse(has_missing)

    def test_normalize_bar_data_drops_non_finite_numeric_rows(self) -> None:
        bars = pd.DataFrame(
            {
                "timestamp_ms": [1_000, 2_000, 3_000],
                "symbol": ["AAPL"] * 3,
                "open": [10.0, np.inf, 12.0],
                "high": [10.5, 11.5, 12.5],
                "low": [9.5, 10.5, 11.5],
                "close": [10.0, 11.0, 12.0],
                "volume": [1_000.0, 1_000.0, 1_000.0],
            }
        )

        normalized = normalize_bar_data(bars=bars, symbol="AAPL")

        self.assertEqual(normalized["timestamp_ms"].tolist(), [1_000, 3_000])
        self.assertTrue(np.isfinite(normalized["open"].to_numpy()).all())


if __name__ == "__main__":
    unittest.main()
