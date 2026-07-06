import unittest
from typing import Any, cast

from domain.enums import (
    AllowedDirections,
    BacktestEngine,
    BacktestRunStatus,
    DataGranularity,
    ExitReason,
    FillTiming,
    GapPolicy,
    IntrabarExitPolicy,
    MarketEventType,
    OrderSide,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
    TradeDirection,
)
from domain.events import BarEvent, TickEvent
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestResult,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
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
        self.assertIsNone(request.exchange)
        self.assertFalse(request.persist_result)
        self.assertIsNone(request.run_metadata)
        self.assertEqual(request.execution.commission_bps, 0.0)
        self.assertEqual(request.execution.slippage_bps, 0.0)
        self.assertEqual(
            request.execution.allowed_directions,
            AllowedDirections.LONG_AND_SHORT,
        )
        self.assertEqual(
            request.execution.intrabar_exit_policy,
            IntrabarExitPolicy.CONSERVATIVE,
        )

    def test_allowed_directions_values_are_explicit(self) -> None:
        self.assertEqual(AllowedDirections.LONG_ONLY.value, "long_only")
        self.assertEqual(AllowedDirections.SHORT_ONLY.value, "short_only")
        self.assertEqual(AllowedDirections.LONG_AND_SHORT.value, "long_and_short")

    def test_execution_config_coerces_allowed_directions_text(self) -> None:
        execution = ExecutionConfig(allowed_directions=cast(Any, "short_only"))

        self.assertEqual(execution.allowed_directions, AllowedDirections.SHORT_ONLY)

    def test_execution_config_rejects_unknown_allowed_directions(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed_directions"):
            ExecutionConfig(allowed_directions=cast(Any, "flat_only"))

    def test_backtest_engine_values_are_explicit(self) -> None:
        self.assertEqual(BacktestEngine.VECTORIZED.value, "vectorized")
        self.assertEqual(BacktestEngine.EVENT_DRIVEN.value, "event_driven")

    def test_exit_reason_values_are_explicit(self) -> None:
        self.assertEqual(ExitReason.SIGNAL.value, "signal")
        self.assertEqual(ExitReason.STOP_LOSS.value, "stop_loss")
        self.assertEqual(ExitReason.TAKE_PROFIT.value, "take_profit")

    def test_trade_direction_values_are_explicit(self) -> None:
        self.assertEqual(TradeDirection.LONG.value, "long")
        self.assertEqual(TradeDirection.SHORT.value, "short")

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
            exchange="NASDAQ",
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
            trade_direction=TradeDirection.LONG,
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

    def test_backtest_request_round_trips_through_versioned_snapshot(self) -> None:
        request = BacktestRequest(
            symbols=["EURUSD"],
            exchange="FX",
            timeframe="M15",
            start_ms=1_714_521_600_000,
            end_ms=1_714_608_000_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={
                    "fast_window": 5,
                    "slow_window": 20,
                    "quantity": 1_000.0,
                    "nested": {"enabled": True},
                },
            ),
            execution=ExecutionConfig(
                signal_timing=SignalTiming.CLOSE,
                fill_timing=FillTiming.NEXT_OPEN,
                price_source=PriceSource.OPEN,
                allow_partial_fills=False,
                allowed_directions=AllowedDirections.SHORT_ONLY,
                trade_accounting_policy=TradeAccountingPolicy.AVERAGE_COST,
                gap_policy=GapPolicy.ERROR,
                intrabar_exit_policy=IntrabarExitPolicy.TAKE_PROFIT_FIRST,
                commission_bps=1.5,
                slippage_bps=0.75,
            ),
            initial_capital=25_000.0,
            data_granularity=DataGranularity.BAR,
            persist_result=True,
            run_metadata={
                "label": "exchange-preservation",
                "tags": ["smoke", "durable"],
            },
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        snapshot = BacktestRequestSnapshot.from_request(request)
        restored = snapshot.to_request()

        self.assertEqual(snapshot.schema_version, 2)
        self.assertEqual(snapshot.payload["exchange"], "FX")
        self.assertEqual(
            snapshot.payload["strategy"]["parameters"],
            request.strategy.parameters,
        )
        self.assertEqual(snapshot.payload["execution"]["allowed_directions"], "short_only")
        self.assertNotIn("allow_short", snapshot.payload["execution"])
        self.assertEqual(snapshot.payload["execution"]["gap_policy"], "error")
        self.assertEqual(
            snapshot.payload["execution"]["intrabar_exit_policy"],
            "take_profit_first",
        )
        self.assertEqual(snapshot.payload["run_metadata"], request.run_metadata)
        self.assertEqual(restored, request)

    def test_backtest_request_snapshot_rejects_unknown_version(self) -> None:
        snapshot = BacktestRequestSnapshot(
            schema_version=99,
            payload={},
        )

        with self.assertRaisesRegex(ValueError, "Unsupported backtest request schema version"):
            snapshot.to_request()

    def test_backtest_request_snapshot_rejects_incomplete_payload(self) -> None:
        snapshot = BacktestRequestSnapshot(
            schema_version=2,
            payload={"symbols": ["EURUSD"]},
        )

        with self.assertRaisesRegex(ValueError, "missing required fields"):
            snapshot.to_request()

    def test_backtest_request_snapshot_rejects_legacy_allow_short(self) -> None:
        request = BacktestRequest(
            symbols=["EURUSD"],
            exchange="FX",
            timeframe="M1",
            start_ms=1_714_521_600_000,
            end_ms=1_714_608_000_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )
        payload = dict(BacktestRequestSnapshot.from_request(request).payload)
        payload["execution"] = {
            **payload["execution"],
            "allow_short": True,
        }

        snapshot = BacktestRequestSnapshot(schema_version=2, payload=payload)

        with self.assertRaisesRegex(ValueError, "unknown fields: allow_short"):
            snapshot.to_request()

    def test_durable_run_contract_types_construct(self) -> None:
        request = BacktestRequest(
            symbols=["EURUSD"],
            exchange="FX",
            timeframe="M1",
            start_ms=1_714_521_600_000,
            end_ms=1_714_608_000_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )
        fill = BacktestFillRecord(
            run_id="run-1",
            sequence=0,
            timestamp_ms=1_714_522_500_000,
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=1_000.0,
            price=1.0715,
            fees=0.15,
        )
        trade = BacktestTradeRecord(
            run_id="run-1",
            sequence=0,
            trade_id="trade-1",
            symbol="EURUSD",
            trade_direction=TradeDirection.LONG,
            quantity=1_000.0,
            entry_timestamp_ms=1_714_522_500_000,
            entry_price=1.0715,
            exit_timestamp_ms=1_714_526_100_000,
            exit_price=1.074,
            realized_pnl=2.5,
            fees=0.15,
            exit_reason=ExitReason.SIGNAL,
        )
        run = BacktestRunRecord(
            run_id="run-1",
            status=BacktestRunStatus.QUEUED,
            submitted_at_ms=1_778_848_205_123,
            request_snapshot=BacktestRequestSnapshot.from_request(request),
        )
        query = BacktestRunQuery(
            status=BacktestRunStatus.QUEUED,
            symbol="EURUSD",
            timeframe="M1",
            strategy_id="sma_crossover",
            engine=BacktestEngine.VECTORIZED,
            submitted_from_ms=1_778_800_000_000,
            submitted_to_ms=1_778_900_000_000,
        )

        self.assertEqual(run.status, BacktestRunStatus.QUEUED)
        self.assertEqual(run.request_snapshot.to_request(), request)
        self.assertEqual(fill.side, OrderSide.BUY)
        self.assertEqual(trade.trade_direction, TradeDirection.LONG)
        self.assertEqual(trade.exit_reason, ExitReason.SIGNAL)
        self.assertEqual(query.engine, BacktestEngine.VECTORIZED)

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
