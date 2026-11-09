import unittest
from dataclasses import replace

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine
from domain.risk import InstrumentSpec, ProtectionSetting, SizingPolicy
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig


class SizedTargetTests(unittest.TestCase):
    def test_engines_size_at_submission_and_replay_same_equity(self):
        prices = [100, 99, 98, 101, 104, 102, 100, 97, 99, 103, 105, 102]
        bars = pd.DataFrame(
            [
                dict(
                    timestamp_ms=i * 60000,
                    symbol="X",
                    open=price,
                    high=price + 0.1,
                    low=price - 0.1,
                    close=price,
                    volume=1,
                )
                for i, price in enumerate(prices)
            ]
        )
        request = BacktestRequest(
            symbols=["X"],
            timeframe="M1",
            start_ms=0,
            end_ms=len(prices) * 60000,
            initial_capital=10000,
            strategy=StrategyConfig("sma_crossover", {"fast_window": 1, "slow_window": 2}, 1),
            execution=ExecutionConfig(
                sizing=SizingPolicy("risk", 100, 10), stop_loss=ProtectionSetting("distance", 10)
            ),
            instrument=InstrumentSpec(1, "USD", 1, 1, 1, 0.01),
        )
        vector = run_backtest(request=request, bars=bars)
        event = run_backtest(
            request=replace(request, engine=BacktestEngine.EVENT_DRIVEN), bars=bars
        )
        self.assertTrue(vector.fills)
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.equity_curve, event.equity_curve)
        self.assertEqual(vector.fills[0].quantity, 10)
        self.assertTrue(
            any(item["outcome"] == "sizing" for item in vector.diagnostics["order_events"])
        )
