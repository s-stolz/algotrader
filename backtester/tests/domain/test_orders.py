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


class MarketIncrementTests(unittest.TestCase):
    def test_tick_protection_resolves_from_saved_market_increment(self):
        from domain.orders import OrderProtection

        protection = OrderProtection(stop_loss_ticks=100, take_profit_ticks=200)
        for min_move in (0.00001, 0.01, 0.25):
            resolved = protection.resolve_ticks(min_move)
            self.assertEqual(resolved.stop_loss_distance, 100 * min_move)
            self.assertEqual(resolved.take_profit_distance, 200 * min_move)
            self.assertIsNone(resolved.stop_loss_ticks)
        for min_move in (None, 0, -1, True, float("inf"), float("nan")):
            with self.subTest(min_move=min_move), self.assertRaises(ValueError):
                protection.resolve_ticks(min_move)

    def test_tick_counts_cannot_mix_with_price_or_percentage_modes(self):
        from domain.orders import OrderProtection

        invalid: list[dict[str, Any]] = [
            {"stop_loss_ticks": 0},
            {"take_profit_ticks": 1.5},
            {"stop_loss_ticks": True},
            {"stop_loss_ticks": 100, "stop_loss_distance": 1},
            {"take_profit_ticks": 200, "take_profit_pct": 2},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OrderProtection(**kwargs)
