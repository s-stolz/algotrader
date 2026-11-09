"""Preservation cases for sized target execution and its independent runtime."""

import unittest

from domain.enums import GapPolicy
from domain.risk import InstrumentSpec, ProtectionSetting, SizingPolicy
from domain.schedule import DailyTradingSchedule
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from engines.sized_targets_event_driven import run_sized_targets as run_events
from engines.sized_targets_vectorized import run_sized_targets as run_arrays
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class SizedTargetArrayTests(unittest.TestCase):
    def request(self, **execution):
        return BacktestRequest(
            symbols=["X"],
            timeframe="M1",
            start_ms=0,
            end_ms=600000,
            initial_capital=1000,
            strategy=StrategyConfig("sma_crossover", {}, 1),
            instrument=InstrumentSpec(1, "USD", 2, 0.1, 0.1, 0.01),
            execution=ExecutionConfig(**execution),
        )

    def compare(self, request, prices, signals, targets):
        decisions = [
            (i * 60000, *bar, signal, (i + 1) * 60000, target)
            for i, (bar, signal, target) in enumerate(zip(prices, signals, targets))
        ]
        strategy = build_sma_crossover_strategy(stop_loss_pct=5, take_profit_pct=10)
        vector = run_arrays(request, strategy, iter(decisions))
        event = run_events(request, strategy, iter(decisions))
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.trades, event.trades)
        self.assertEqual(len(vector.equity_curve), len(event.equity_curve))
        for left, right in zip(vector.equity_curve, event.equity_curve):
            self.assertEqual(left.timestamp_ms, right.timestamp_ms)
            self.assertEqual(left.positions, right.positions)
            self.assertAlmostEqual(left.cash, right.cash)
            self.assertAlmostEqual(left.equity, right.equity)
        for key in ("order_events", "termination_reason", "intrabar_ambiguous_bar_count"):
            self.assertEqual(vector.diagnostics[key], event.diagnostics[key])
        return vector

    def test_sizing_modes_preserve_reversal_reduction_and_costs(self):
        prices = [(p, p + 1, p - 1, p) for p in (100, 101, 102, 103, 102, 101, 100, 99)]
        for mode, value in (
            ("strategy", None),
            ("units", 2),
            ("exposure", 400),
            ("equity_exposure", 40),
            ("risk", 20),
            ("equity_risk", 2),
        ):
            with self.subTest(mode=mode):
                self.compare(
                    self.request(
                        sizing=SizingPolicy(mode, value, 10),
                        stop_loss=ProtectionSetting("distance", 10),
                        commission_bps=2,
                        slippage_bps=3,
                    ),
                    prices,
                    [1, 0, 1, 1, -1, 0, 2, 0],
                    [2, 2, 4, 1, -2, -2, 0, 0],
                )

    def test_shared_protection_gaps_schedule_and_ambiguous_paths(self):
        prices = [(100, 101, 99, 100)] * 8
        prices[3] = (100, 120, 80, 100)
        for policy in ("conservative", "take_profit_first"):
            from domain.enums import IntrabarExitPolicy

            self.compare(
                self.request(
                    sizing=SizingPolicy("units", 2, 10),
                    stop_loss=ProtectionSetting("distance", 5),
                    take_profit=ProtectionSetting("distance", 10),
                    intrabar_exit_policy=IntrabarExitPolicy(policy),
                ),
                prices,
                [1, 0, 0, 0, -1, 0, 0, 0],
                [2, 2, 2, 2, -2, -2, -2, -2],
            )
        prices = [(100, 100, 100, 100)] * 8
        prices[1] = (0, 100, 0, 100)
        for gap in (GapPolicy.SKIP, GapPolicy.EXPIRE):
            self.compare(
                self.request(
                    sizing=SizingPolicy("units", 2, 10),
                    gap_policy=gap,
                    daily_schedule=DailyTradingSchedule(0, 4, 5),
                ),
                prices,
                [1, 0, 1, 0, 0, 0, 0, 0],
                [2] * 8,
            )

    def test_depletion_and_rejected_entries(self):
        prices = [(100, 100, 100, 100)] * 6
        prices[4] = (20, 30, 10, 25)
        result = self.compare(
            self.request(sizing=SizingPolicy("units", 10, 10), stop_loss=ProtectionSetting("none")),
            prices,
            [1, 0, 0, 0, 0, 0],
            [10] * 6,
        )
        self.assertEqual(result.diagnostics["termination_reason"], "account_depleted")
        self.assertEqual(len(result.equity_curve), 5)
        self.compare(
            self.request(sizing=SizingPolicy("units", 10, 1)), prices, [1, 0, 0, 0, 0, 0], [10] * 6
        )

    def test_empty_execution_rejected(self):
        strategy = build_sma_crossover_strategy()
        for run in (run_arrays, run_events):
            with self.assertRaisesRegex(ValueError, "No executable bars"):
                run(self.request(sizing=SizingPolicy()), strategy, iter([]))
