import unittest

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine, DataGranularity
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig


class TestEventDrivenBacktestIntegration(unittest.TestCase):
    def _build_bars(self) -> pd.DataFrame:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
        opens = [10.0, 9.0, 8.0, 9.0, 99.0, 10.0, 11.0, 12.0, 13.0]

        return pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": opens,
                "high": [max(open_price, close) + 0.5 for open_price, close in zip(opens, closes)],
                "low": [min(open_price, close) - 0.5 for open_price, close in zip(opens, closes)],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )

    def _build_request(self) -> BacktestRequest:
        return BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

    def test_event_driven_sma_crossover_runs_and_fills_next_open(self) -> None:
        result = run_backtest(request=self._build_request(), bars=self._build_bars())

        self.assertEqual(result.diagnostics["engine"], "event_driven")
        self.assertEqual(result.diagnostics["strategy_id"], "sma_crossover")
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].timestamp_ms, 1_700_000_300_000)
        self.assertEqual(result.fills[0].price, 10.0)
        self.assertEqual(result.fills[1].timestamp_ms, 1_700_000_480_000)
        self.assertEqual(result.fills[1].price, 13.0)
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].realized_pnl, 3.0)
        self.assertEqual(result.equity_curve[-1].equity, 10_003.0)
        self.assertAlmostEqual(result.metrics["trade_count"], 1.0)

    def test_final_bar_decision_expires_without_out_of_range_fill(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(5)],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 9.0, 8.0, 9.0, 99.0],
                "high": [10.5, 9.5, 8.5, 9.5, 99.5],
                "low": [9.5, 8.5, 7.5, 8.5, 98.5],
                "close": [10.0, 9.0, 8.0, 9.0, 10.0],
                "volume": [1_000.0] * 5,
            }
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=start_ms,
            end_ms=start_ms + (5 * minute),
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        result = run_backtest(request=request, bars=bars)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.trades, [])
        self.assertEqual(result.diagnostics["tail_expired_delta_count"], 1)
        self.assertEqual(result.equity_curve[-1].equity, 10_000.0)

    def test_event_driven_rejects_multi_symbol_requests(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL", "MSFT"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        with self.assertRaisesRegex(ValueError, "exactly one symbol"):
            run_backtest(request=request, bars=self._build_bars())

    def test_event_driven_rejects_non_bar_requests(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
            data_granularity=DataGranularity.TICK,
        )

        with self.assertRaisesRegex(ValueError, "event-driven execution"):
            run_backtest(request=request, bars=self._build_bars())


if __name__ == "__main__":
    unittest.main()
