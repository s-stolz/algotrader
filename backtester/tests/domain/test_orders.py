"""Order request validation and immutable snapshot compatibility."""

import unittest
from typing import Any

from domain.enums import IntrabarExitPolicy
from domain.orders import IntrabarExecutionPolicy
from domain.types import BacktestRequest, BacktestRequestSnapshot, ExecutionConfig, StrategyConfig


class OrderContractTests(unittest.TestCase):
    def test_explicit_quote_required(self):
        with self.assertRaisesRegex(ValueError, "candle_quote"):
            ExecutionConfig(execution_mode="orders")

    def test_general_policy_maps_to_legacy_protection(self):
        config = ExecutionConfig(intrabar_execution_policy=IntrabarExecutionPolicy.OPTIMISTIC)
        self.assertEqual(config.intrabar_exit_policy, IntrabarExitPolicy.TAKE_PROFIT_FIRST)

    def test_snapshot_roundtrip(self):
        request = BacktestRequest(
            symbols=["TEST"],
            timeframe="M10",
            start_ms=0,
            end_ms=600_000,
            strategy=StrategyConfig("test", strategy_version=1),
            initial_capital=1000,
            execution=ExecutionConfig(
                execution_mode="orders",
                candle_quote="mid",
                spread=0.2,
                max_position_quantity=10,
                intrabar_execution_policy=IntrabarExecutionPolicy.ERROR,
            ),
        )
        self.assertEqual(BacktestRequestSnapshot.from_request(request).to_request(), request)

    def test_target_mode_rejects_unused_costs(self):
        with self.assertRaisesRegex(ValueError, "require order execution"):
            ExecutionConfig(spread=1)


class DistanceProtectionTests(unittest.TestCase):
    def test_rejects_conflicting_and_invalid_distances(self):
        from domain.orders import OrderProtection, TakeProfitTier

        invalid: list[dict[str, Any]] = [
            {"stop_loss_distance": 0},
            {"take_profit_distance": float("nan")},
            {"stop_loss_distance": 1, "stop_price": 95},
            {"stop_loss_distance": 1, "stop_loss_pct": 2},
            {"take_profit_distance": 1, "take_profit_pct": 2},
            {"take_profit_distance": 1, "take_profits": (TakeProfitTier(110, fraction=1),)},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OrderProtection(**kwargs)
