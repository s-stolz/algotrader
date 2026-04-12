import unittest

import pandas as pd
from data.market_data import load_market_data
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class _FakeHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        _ = kwargs
        return self._bars.copy()


class TestMarketDataPipeline(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
