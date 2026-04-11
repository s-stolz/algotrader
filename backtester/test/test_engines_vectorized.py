import unittest
from unittest.mock import patch

import pandas as pd
from app.backtest_runner import run_backtest
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class TestVectorizedBacktestIntegration(unittest.TestCase):
    def _build_bars(self) -> pd.DataFrame:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
        opens = [10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0]

        return pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": opens,
                "high": [price + 0.5 for price in opens],
                "low": [price - 0.5 for price in opens],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )

    def _build_request(self) -> BacktestRequest:
        return BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_480_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

    def test_fixture_bars_produce_deterministic_result(self) -> None:
        bars = self._build_bars()
        request = self._build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].price, 10.0)
        self.assertEqual(result.fills[1].price, 13.0)
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].realized_pnl, 3.0)
        self.assertEqual(result.equity_curve[-1].equity, 10_003.0)
        self.assertAlmostEqual(result.metrics["trade_count"], 1.0)

    def test_vectorized_engine_does_not_use_row_iterators(self) -> None:
        bars = self._build_bars()
        request = self._build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch.object(pd.DataFrame, "iterrows", side_effect=AssertionError("iterrows called")):
            with patch.object(
                pd.DataFrame,
                "itertuples",
                side_effect=AssertionError("itertuples called"),
            ):
                result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(len(result.fills), 2)


if __name__ == "__main__":
    unittest.main()
