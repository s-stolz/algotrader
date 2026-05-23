import unittest
from typing import Any, cast

from domain.enums import (
    BacktestEngine,
    DataGranularity,
    ExitReason,
    IntrabarExitPolicy,
    MarketEventType,
    OrderSide,
)
from domain.events import BarEvent, TickEvent
from domain.types import (
    BacktestRequest,
    BacktestResult,
    ExecutionArrayBundle,
    ExecutionConfig,
    FeatureMatrix,
    Fill,
    PortfolioSnapshot,
    SignalMatrix,
    StrategyConfig,
    Trade,
)


class TestDomainTypes(unittest.TestCase):
    def test_backtest_request_defaults(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_360_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

        self.assertEqual(request.data_granularity, DataGranularity.BAR)
        self.assertEqual(request.engine, BacktestEngine.VECTORIZED)
        self.assertFalse(request.persist_result)
        self.assertIsNone(request.run_metadata)
        self.assertEqual(request.execution.commission_bps, 0.0)
        self.assertEqual(request.execution.slippage_bps, 0.0)
        self.assertEqual(
            request.execution.intrabar_exit_policy,
            IntrabarExitPolicy.CONSERVATIVE,
        )

    def test_backtest_engine_values_are_explicit(self) -> None:
        self.assertEqual(BacktestEngine.VECTORIZED.value, "vectorized")
        self.assertEqual(BacktestEngine.EVENT_DRIVEN.value, "event_driven")

    def test_exit_reason_values_are_explicit(self) -> None:
        self.assertEqual(ExitReason.SIGNAL.value, "signal")
        self.assertEqual(ExitReason.STOP_LOSS.value, "stop_loss")
        self.assertEqual(ExitReason.TAKE_PROFIT.value, "take_profit")

    def test_intrabar_exit_policy_values_are_explicit(self) -> None:
        self.assertEqual(IntrabarExitPolicy.CONSERVATIVE.value, "conservative")
        self.assertEqual(IntrabarExitPolicy.STOP_FIRST.value, "stop_first")
        self.assertEqual(IntrabarExitPolicy.TAKE_PROFIT_FIRST.value, "take_profit_first")
        self.assertEqual(IntrabarExitPolicy.ERROR.value, "error")

    def test_execution_config_coerces_intrabar_exit_policy_text(self) -> None:
        execution = ExecutionConfig(intrabar_exit_policy=cast(Any, "take_profit_first"))

        self.assertEqual(
            execution.intrabar_exit_policy,
            IntrabarExitPolicy.TAKE_PROFIT_FIRST,
        )

    def test_execution_config_rejects_unknown_intrabar_exit_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "intrabar_exit_policy"):
            ExecutionConfig(intrabar_exit_policy=cast(Any, "optimistic"))

    def test_vectorized_contract_types_construct(self) -> None:
        feature_matrix = FeatureMatrix(
            timestamp_ms=[1, 2, 3],
            features_by_symbol={"AAPL": {"sma_fast": [1.0, 2.0, 3.0], "sma_slow": [1.5, 1.7, 2.1]}},
        )
        signal_matrix = SignalMatrix(timestamp_ms=[1, 2, 3], signals_by_symbol={"AAPL": [0, 1, 1]})
        execution_bundle = ExecutionArrayBundle(
            timestamp_ms=[1, 2, 3],
            target_quantity_by_symbol={"AAPL": [0.0, 1.0, 1.0]},
        )

        self.assertEqual(feature_matrix.timestamp_ms, [1, 2, 3])
        self.assertEqual(signal_matrix.signals_by_symbol["AAPL"], [0, 1, 1])
        self.assertEqual(execution_bundle.target_quantity_by_symbol["AAPL"], [0.0, 1.0, 1.0])

    def test_result_types_construct(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_360_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            persist_result=True,
            run_metadata={"label": "m0-smoke"},
        )
        fill = Fill(
            timestamp_ms=1_700_000_060_000,
            symbol="AAPL",
            quantity=1.0,
            price=101.5,
            side=OrderSide.BUY,
            fees=0.1,
        )
        trade = Trade(
            trade_id="trade-1",
            symbol="AAPL",
            quantity=1.0,
            entry_timestamp_ms=1_700_000_060_000,
            entry_price=101.5,
        )
        snapshot = PortfolioSnapshot(
            timestamp_ms=1_700_000_120_000,
            cash=9_898.4,
            equity=10_001.0,
            positions={"AAPL": 1.0},
        )
        result = BacktestResult(
            request=request,
            fills=[fill],
            trades=[trade],
            equity_curve=[snapshot],
            metrics={"return_pct": 0.01},
            diagnostics={"engine": "vectorized"},
            backtest_run_id="run-1",
            persisted_at=1_700_000_130_000,
        )

        self.assertEqual(result.request.strategy.strategy_id, "sma_crossover")
        self.assertEqual(result.fills[0].side, OrderSide.BUY)
        self.assertEqual(result.backtest_run_id, "run-1")
        self.assertEqual(result.metrics["return_pct"], 0.01)
        self.assertEqual(result.trades[0].fees, 0.0)
        self.assertEqual(result.trades[0].exit_reason, ExitReason.SIGNAL)

    def test_event_types_construct(self) -> None:
        bar_event = BarEvent(
            timestamp_ms=1_700_000_000_000,
            symbol="AAPL",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=10_000.0,
        )
        tick_event = TickEvent(
            timestamp_ms=1_700_000_000_500,
            symbol="AAPL",
            bid=100.45,
            ask=100.55,
            last=100.5,
            size=100.0,
        )

        self.assertEqual(bar_event.event_type, MarketEventType.BAR)
        self.assertEqual(tick_event.event_type, MarketEventType.TICK)

    def test_execution_config_rejects_negative_cost_inputs(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionConfig(commission_bps=-1.0)

        with self.assertRaises(ValueError):
            ExecutionConfig(slippage_bps=-0.5)

    def test_execution_config_rejects_non_finite_cost_inputs(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionConfig(commission_bps=float("nan"))

        with self.assertRaises(ValueError):
            ExecutionConfig(slippage_bps=float("nan"))

        with self.assertRaises(ValueError):
            ExecutionConfig(commission_bps=float("inf"))

        with self.assertRaises(ValueError):
            ExecutionConfig(slippage_bps=float("-inf"))


if __name__ == "__main__":
    unittest.main()
