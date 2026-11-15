import unittest
from dataclasses import replace

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine
from domain.progress import observe_progress
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
        vector_stages, event_stages = [], []
        vector_counts, event_counts = [], []
        with observe_progress(
            vector_stages.append, lambda done, total: vector_counts.append((done, total))
        ):
            vector = run_backtest(request=request, bars=bars)
        with observe_progress(
            event_stages.append, lambda done, total: event_counts.append((done, total))
        ):
            event = run_backtest(
                request=replace(request, engine=BacktestEngine.EVENT_DRIVEN), bars=bars
            )
        self.assertEqual(
            vector_stages, ["preparing_indicators", "simulating", "calculating_results"]
        )
        self.assertEqual(event_stages, vector_stages)
        self.assertEqual(vector_counts, [])
        self.assertEqual(event_counts, [(0, len(bars)), (len(bars), len(bars))])
        self.assertIn("profit_factor", vector.metrics)
        self.assertEqual(vector.metrics, event.metrics)
        self.assertTrue(vector.fills)
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.equity_curve, event.equity_curve)
        self.assertEqual(vector.fills[0].quantity, 10)
        self.assertTrue(
            any(item["outcome"] == "sizing" for item in vector.diagnostics["order_events"])
        )

        depleted_bars = bars.copy()
        depleted_bars.loc[5:, ["open", "high", "low", "close"]] = 1.0
        depleted_request = replace(
            request,
            engine=BacktestEngine.EVENT_DRIVEN,
            initial_capital=100,
            execution=ExecutionConfig(
                sizing=SizingPolicy("units", 10, 100), stop_loss=ProtectionSetting("none")
            ),
        )
        counts = []
        with observe_progress(lambda stage: None, lambda done, total: counts.append((done, total))):
            depleted = run_backtest(request=depleted_request, bars=depleted_bars)
        self.assertEqual(depleted.diagnostics["termination_reason"], "account_depleted")
        self.assertEqual(counts[-1], (6, len(bars)))
