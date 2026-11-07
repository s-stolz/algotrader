"""Registered strategy runs with computed indicators and saved chart metadata."""

import unittest
from dataclasses import replace

import numpy as np
import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig


class RsiRangeBacktestTests(unittest.TestCase):
    def test_registered_strategy_computes_features_and_saves_both_indicators(self):
        prices = 100 + 10 * np.sin(np.arange(100) / 3)
        bars = pd.DataFrame(
            {
                "timestamp_ms": np.arange(100) * 60000,
                "symbol": "TEST",
                "open": prices,
                "high": prices + 2,
                "low": prices - 2,
                "close": prices,
                "volume": 1.0,
            }
        )
        request = BacktestRequest(
            symbols=["TEST"],
            timeframe="M1",
            start_ms=0,
            end_ms=6000000,
            initial_capital=10000,
            strategy=StrategyConfig(
                "rsi_range_limit", {"tick_size": 0.01, "rsi_period": 2, "range_period": 3}, 1
            ),
            execution=ExecutionConfig(execution_mode="orders", candle_quote="bid"),
        )
        vector = run_backtest(request=request, bars=bars)
        event = run_backtest(
            request=replace(request, engine=BacktestEngine.EVENT_DRIVEN), bars=bars
        )
        self.assertTrue(vector.fills)
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.trades, event.trades)
        self.assertEqual(vector.diagnostics["order_events"], event.diagnostics["order_events"])
        self.assertEqual(
            vector.diagnostics["chart_indicators"], event.diagnostics["chart_indicators"]
        )
        indicators = vector.diagnostics["chart_indicators"]["items"]
        self.assertEqual(len(indicators), 2)
        self.assertEqual({item["indicator_id"] for item in indicators}, {"rsi", "rolling_range"})
