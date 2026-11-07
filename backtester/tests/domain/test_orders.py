"""Order request validation and immutable snapshot compatibility."""

import unittest

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
