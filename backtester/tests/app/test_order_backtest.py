"""Order-mode integration, causality, independent runtimes, and minute replay."""

import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pandas as pd
from app.backtest_runner import run_backtest, run_backtest_with_market_data
from app.equity_replay import descriptor
from domain.enums import BacktestEngine, GapPolicy
from domain.orders import IntrabarExecutionPolicy
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.limit_reversion import build_limit_reversion


def candles(timestamps, lows=None):
    return pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "symbol": "TEST",
            "open": 100.0,
            "high": 100.5,
            "low": lows if lows is not None else 99.5,
            "close": 100.0,
            "volume": 1.0,
        }
    )


class OrderBacktestTests(unittest.TestCase):
    def setUp(self):
        self.request = BacktestRequest(
            symbols=["TEST"],
            timeframe="M10",
            start_ms=0,
            end_ms=1_800_000,
            strategy=StrategyConfig("limit_reversion", strategy_version=1),
            initial_capital=10_000,
            execution=ExecutionConfig(execution_mode="orders", candle_quote="bid"),
        )
        self.strategy = build_limit_reversion(quantity=2)
        self.bars = candles([0, 600_000, 1_200_000])
        self.minutes = candles(list(range(0, 1_800_000, 60_000)))
        self.minutes.loc[11, "low"] = 98.5

    def run_engine(self, engine, minutes=None):
        return run_backtest(
            request=replace(self.request, engine=engine),
            bars=self.bars,
            execution_bars=self.minutes if minutes is None else minutes,
            strategy=self.strategy,
        )

    def test_engine_parity_and_no_retroactive_entry(self):
        self.minutes.loc[2, "low"] = 98.5
        vector = self.run_engine(BacktestEngine.VECTORIZED)
        event = self.run_engine(BacktestEngine.EVENT_DRIVEN)
        self.assertTrue(vector.fills)
        self.assertEqual(vector.fills[0].timestamp_ms, 660_000)
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.trades, event.trades)
        self.assertEqual(vector.equity_curve, event.equity_curve)
        self.assertEqual(vector.diagnostics["order_events"], event.diagnostics["order_events"])
        self.assertEqual(
            vector.replay_descriptor,
            descriptor(
                self.request,
                [
                    (int(ts), float(close))
                    for ts, close in self.minutes[["timestamp_ms", "close"]].itertuples(
                        index=False, name=None
                    )
                ],
            ),
        )

    def test_event_runtime_does_not_call_array_execution(self):
        with (
            patch("execution.order_scan.scan_orders", side_effect=AssertionError("vector scan")),
            patch("execution.orders.execute_minute", side_effect=AssertionError("vector matcher")),
            patch(
                "execution.portfolio.build_equity_curve",
                side_effect=AssertionError("array accounting"),
            ),
        ):
            self.assertTrue(self.run_engine(BacktestEngine.EVENT_DRIVEN).fills)

    def test_higher_timeframe_requires_minute_data(self):
        with self.assertRaisesRegex(ValueError, "explicit M1"):
            run_backtest(request=self.request, bars=self.bars, strategy=self.strategy)

    def test_missing_minute_data_is_explicit(self):
        missing = self.minutes.drop(index=10)
        for engine in BacktestEngine:
            result = self.run_engine(engine, missing)
            self.assertTrue(
                any(
                    item["outcome"] == "execution_gap"
                    for item in result.diagnostics["order_events"]
                )
            )
        self.request = replace(
            self.request, execution=replace(self.request.execution, gap_policy=GapPolicy.ERROR)
        )
        with self.assertRaisesRegex(ValueError, "Missing minute"):
            self.run_engine(BacktestEngine.VECTORIZED, missing)

    def test_loader_fetches_both_resolutions(self):
        frames = {"M10": self.bars, "M1": self.minutes}
        calls = []

        class Adapter:
            def fetch_bars(self, **kwargs):
                calls.append(kwargs["timeframe"])
                return frames[kwargs["timeframe"]]

        result = run_backtest_with_market_data(
            request=self.request, strategy=self.strategy, data_adapter=Adapter()
        )
        self.assertEqual(calls, ["M10", "M1"])
        self.assertTrue(result.fills)

    def test_spread_and_costs_preserve_parity(self):
        self.request = replace(
            self.request,
            execution=replace(self.request.execution, spread=0.1, slippage_bps=2, commission_bps=1),
        )
        vector, event = (self.run_engine(engine) for engine in BacktestEngine)
        self.assertEqual(vector.fills, event.fills)
        np.testing.assert_allclose(
            [p.equity for p in vector.equity_curve], [p.equity for p in event.equity_curve]
        )


class OrderPathParityTests(unittest.TestCase):
    def test_seeded_prices_and_both_path_policies_match(self):
        rng = np.random.default_rng(52)
        timestamps = np.arange(120) * 60_000
        prices = 100 + np.cumsum(rng.normal(0, 0.3, 120))
        minutes = candles(timestamps)
        minutes["open"] = prices
        minutes["close"] = prices + rng.normal(0, 0.1, 120)
        minutes["high"] = minutes[["open", "close"]].max(axis=1) + 1.2
        minutes["low"] = minutes[["open", "close"]].min(axis=1) - 1.2
        strategy_bars = candles(timestamps[::5])
        for policy in ("conservative", "optimistic"):
            request = BacktestRequest(
                symbols=["TEST"],
                timeframe="M5",
                start_ms=0,
                end_ms=7_200_000,
                strategy=StrategyConfig("limit_reversion", strategy_version=1),
                execution=ExecutionConfig(
                    execution_mode="orders",
                    candle_quote="mid",
                    spread=0.02,
                    intrabar_execution_policy=IntrabarExecutionPolicy(policy),
                    max_entries_per_day=12,
                ),
                initial_capital=10_000,
            )
            results = [
                run_backtest(
                    request=replace(request, engine=engine),
                    bars=strategy_bars,
                    execution_bars=minutes,
                    strategy=build_limit_reversion(),
                )
                for engine in BacktestEngine
            ]
            self.assertEqual(results[0].fills, results[1].fills)
            self.assertEqual(results[0].trades, results[1].trades)
            np.testing.assert_allclose(
                [point.equity for point in results[0].equity_curve],
                [point.equity for point in results[1].equity_curve],
            )
