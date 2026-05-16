import ast
import inspect
import sys
import unittest
from pathlib import Path

import engines.event_driven as event_driven_engine
import numpy as np
import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine, DataGranularity, GapPolicy, PriceSource
from domain.types import (
    BacktestRequest,
    BacktestResult,
    ExecutionConfig,
    StrategyConfig,
)
from strategies.base import BarStrategyModel, IndicatorFeatureRequirement, StrategyDefinition
from strategies.conditions import ConditionRule


class TestEventDrivenBacktestIntegration(unittest.TestCase):
    def _build_bars(self) -> pd.DataFrame:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
        opens = [10.0, 9.0, 8.0, 9.0, 99.0, 10.0, 11.0, 12.0, 13.0]

        return pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": opens,
                "high": [max(open_price, close) + 0.5 for open_price, close in zip(opens, closes)],
                "low": [min(open_price, close) - 0.5 for open_price, close in zip(opens, closes)],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )

    def _build_request(
        self,
        *,
        engine: BacktestEngine = BacktestEngine.EVENT_DRIVEN,
        execution: ExecutionConfig | None = None,
        strategy: StrategyConfig | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> BacktestRequest:
        base_start_ms = 1_700_000_000_000
        minute = 60_000
        return BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=start_ms if start_ms is not None else base_start_ms + (3 * minute),
            end_ms=end_ms if end_ms is not None else base_start_ms + (9 * minute),
            strategy=(
                strategy
                or StrategyConfig(
                    strategy_id="sma_crossover",
                    parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
                )
            ),
            execution=execution or ExecutionConfig(),
            initial_capital=10_000.0,
            engine=engine,
        )

    def _build_gap_bars(self) -> pd.DataFrame:
        bars = self._build_bars()
        bars.loc[bars["timestamp_ms"] == 1_700_000_240_000, "open"] = 9.0
        bars.loc[bars["timestamp_ms"] == 1_700_000_300_000, "open"] = 0.0
        return bars

    def test_event_driven_sma_crossover_runs_and_fills_next_open(self) -> None:
        result = run_backtest(request=self._build_request(), bars=self._build_bars())

        self.assertEqual(result.diagnostics["engine"], "event_driven")
        self.assertEqual(result.diagnostics["strategy_id"], "sma_crossover")
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].timestamp_ms, 1_700_000_300_000)
        self.assertEqual(result.fills[0].price, 10.0)
        self.assertEqual(result.fills[1].timestamp_ms, 1_700_000_480_000)
        self.assertEqual(result.fills[1].price, 13.0)
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].realized_pnl, 3.0)
        self.assertEqual(result.equity_curve[-1].equity, 10_003.0)
        self.assertAlmostEqual(result.metrics["trade_count"], 1.0)

    def test_event_driven_engine_does_not_call_vectorized_execution_helpers(self) -> None:
        tree = ast.parse(inspect.getsource(event_driven_engine))
        forbidden_calls: list[int] = []
        forbidden_imports: list[int] = []
        forbidden_imports_by_module = {
            "execution": {"generate_fills_from_targets", "build_equity_curve"},
            "execution.fills": {"generate_fills_from_targets"},
            "execution.portfolio": {"build_equity_curve"},
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                forbidden_names = forbidden_imports_by_module.get(node.module or "")
                if forbidden_names and any(alias.name in forbidden_names for alias in node.names):
                    forbidden_imports.append(node.lineno)
            if isinstance(node, ast.Call):
                call = node.func
                if isinstance(call, ast.Name) and call.id == "generate_fills_from_targets":
                    forbidden_calls.append(node.lineno)
                if isinstance(call, ast.Attribute) and call.attr == "generate_fills_from_targets":
                    forbidden_calls.append(node.lineno)
                if isinstance(call, ast.Name) and call.id == "build_equity_curve":
                    forbidden_calls.append(node.lineno)
                if isinstance(call, ast.Attribute) and call.attr == "build_equity_curve":
                    forbidden_calls.append(node.lineno)

        self.assertEqual(forbidden_imports, [])
        self.assertEqual(forbidden_calls, [])

    def test_indicator_strategy_requires_complete_pre_start_bootstrap(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Event-driven.*insufficient warmup.*sma_fast.*sma_slow",
        ):
            run_backtest(
                request=self._build_request(start_ms=1_700_000_000_000),
                bars=self._build_bars(),
            )

    def test_no_indicator_strategy_starts_at_first_in_window_bar_without_bootstrap(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + (minute * i) for i in range(3)],
                "symbol": ["AAPL"] * 3,
                "open": [10.0, 12.0, 13.0],
                "high": [11.5, 12.5, 13.5],
                "low": [9.5, 11.5, 12.5],
                "close": [11.0, 12.0, 13.0],
                "volume": [1_000.0] * 3,
            }
        )
        strategy = _build_enter_and_hold_strategy()

        result = run_backtest(
            request=self._build_request(
                strategy=StrategyConfig(strategy_id=strategy.strategy_id),
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self.assertEqual(result.fills[0].timestamp_ms, start_ms + minute)
        self.assertEqual(result.fills[0].price, 12.0)
        self.assertEqual(
            [snapshot.timestamp_ms for snapshot in result.equity_curve],
            [start_ms, start_ms + minute, start_ms + (2 * minute)],
        )

    def test_bootstrap_bars_do_not_emit_public_execution_results(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + (minute * i) for i in range(7)],
                "symbol": ["AAPL"] * 7,
                "open": [10.0, 9.0, 8.0, 12.0, 13.0, 14.0, 15.0],
                "high": [10.5, 9.5, 8.5, 12.5, 13.5, 14.5, 15.5],
                "low": [9.5, 8.5, 7.5, 11.5, 12.5, 13.5, 14.5],
                "close": [10.0, 9.0, 8.0, 12.0, 13.0, 14.0, 15.0],
                "volume": [1_000.0] * 7,
            }
        )

        result = run_backtest(
            request=self._build_request(
                start_ms=start_ms + (4 * minute),
                end_ms=start_ms + (7 * minute),
            ),
            bars=bars,
        )

        self.assertEqual(result.fills, [])
        self.assertEqual(result.trades, [])
        self.assertEqual(
            [snapshot.timestamp_ms for snapshot in result.equity_curve],
            [
                start_ms + (4 * minute),
                start_ms + (5 * minute),
                start_ms + (6 * minute),
            ],
        )

    def test_first_tradable_crossover_uses_last_bootstrap_snapshot(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + (minute * i) for i in range(5)],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 9.0, 8.0, 12.0, 15.0],
                "high": [10.5, 9.5, 8.5, 12.5, 15.5],
                "low": [9.5, 8.5, 7.5, 11.5, 14.5],
                "close": [10.0, 9.0, 8.0, 12.0, 13.0],
                "volume": [1_000.0] * 5,
            }
        )

        result = run_backtest(
            request=self._build_request(
                start_ms=start_ms + (3 * minute),
                end_ms=start_ms + (5 * minute),
            ),
            bars=bars,
        )

        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].timestamp_ms, start_ms + (4 * minute))
        self.assertEqual(result.fills[0].price, 15.0)
        self.assertEqual(result.diagnostics["nonzero_signal_count"], 1)

    def test_runtime_invalid_indicator_feature_fails_after_successful_bootstrap(self) -> None:
        _register_runtime_invalid_indicator()
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + (minute * i) for i in range(3)],
                "symbol": ["AAPL"] * 3,
                "open": [10.0, 20.0, 21.0],
                "high": [10.5, 20.5, 21.5],
                "low": [9.5, 19.5, 20.5],
                "close": [10.0, 20.0, 21.0],
                "volume": [1_000.0] * 3,
            }
        )
        strategy = _build_runtime_invalid_feature_strategy()

        with self.assertRaisesRegex(
            ValueError,
            "Event-driven.*runtime invalid feature.*timestamp_ms "
            f"{start_ms + minute}.*symbol AAPL.*runtime_bad",
        ) as raised:
            run_backtest(
                request=self._build_request(
                    strategy=StrategyConfig(strategy_id=strategy.strategy_id),
                    start_ms=start_ms + minute,
                    end_ms=start_ms + (3 * minute),
                ),
                bars=bars,
                strategy=strategy,
            )

        self.assertNotIn("insufficient warmup", str(raised.exception))

    def test_event_driven_diagnostics_include_sequential_processing_counters(self) -> None:
        result = run_backtest(request=self._build_request(), bars=self._build_bars())

        self.assertEqual(result.diagnostics["processed_bar_count"], 9)
        self.assertEqual(result.diagnostics["feature_snapshot_count"], 7)
        self.assertEqual(result.diagnostics["executable_bar_count"], 6)
        self.assertEqual(result.diagnostics["nonzero_signal_count"], 2)

    def test_gap_skip_costs_trades_equity_and_metrics_match_vectorized(self) -> None:
        bars = self._build_gap_bars()
        execution = ExecutionConfig(
            gap_policy=GapPolicy.SKIP,
            commission_bps=20.0,
            slippage_bps=10.0,
        )

        vectorized = run_backtest(
            request=self._build_request(
                engine=BacktestEngine.VECTORIZED,
                execution=execution,
            ),
            bars=bars,
        )
        event_driven = run_backtest(
            request=self._build_request(execution=execution),
            bars=bars,
        )

        self._assert_public_execution_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills[0].timestamp_ms, 1_700_000_360_000)
        self.assertEqual(event_driven.diagnostics["invalid_open_count"], 1)
        self.assertEqual(event_driven.diagnostics["deferred_delta_count"], 1)
        self.assertEqual(event_driven.diagnostics["executed_deferred_count"], 1)
        self.assertGreater(event_driven.diagnostics["total_fees"], 0.0)
        self.assertGreater(event_driven.diagnostics["total_slippage_cost"], 0.0)

    def test_gap_skip_can_net_deferred_pending_delta_to_zero_before_execution(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + (minute * i) for i in range(3)],
                "symbol": ["AAPL"] * 3,
                "open": [10.0, 0.0, 13.0],
                "high": [10.0, 100.0, 100.0],
                "low": [0.0, 9.0, 0.0],
                "close": [11.0, 8.0, 12.0],
                "volume": [1_000.0] * 3,
            }
        )
        strategy = _build_entry_then_exit_feature_strategy()

        result = run_backtest(
            request=self._build_request(
                execution=ExecutionConfig(gap_policy=GapPolicy.SKIP),
                strategy=StrategyConfig(strategy_id=strategy.strategy_id),
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self.assertEqual(result.fills, [])
        self.assertEqual(result.trades, [])
        self.assertEqual(result.equity_curve[-1].positions, {})
        self.assertEqual(result.equity_curve[-1].equity, 10_000.0)
        self.assertEqual(result.diagnostics["invalid_open_count"], 1)
        self.assertEqual(result.diagnostics["deferred_delta_count"], 1)
        self.assertEqual(result.diagnostics["executed_deferred_count"], 0)
        self.assertEqual(result.diagnostics["tail_expired_delta_count"], 0)

    def test_gap_expire_matches_vectorized_without_inventing_executions(self) -> None:
        bars = self._build_gap_bars()
        execution = ExecutionConfig(gap_policy=GapPolicy.EXPIRE)
        strategy = _build_enter_and_hold_strategy()
        config = StrategyConfig(strategy_id=strategy.strategy_id)

        vectorized = run_backtest(
            request=self._build_request(
                engine=BacktestEngine.VECTORIZED,
                execution=execution,
                strategy=config,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=self._build_request(execution=execution, strategy=config),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_execution_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills, [])
        self.assertEqual(event_driven.diagnostics["expired_delta_count"], 1)

    def test_gap_error_matches_vectorized_failure(self) -> None:
        bars = self._build_gap_bars()
        execution = ExecutionConfig(gap_policy=GapPolicy.ERROR)

        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine):
                with self.assertRaisesRegex(ValueError, "Missing valid next-bar open"):
                    run_backtest(
                        request=self._build_request(engine=engine, execution=execution),
                        bars=bars,
                    )

    def test_unsupported_execution_settings_fail_clearly_in_event_driven_mode(self) -> None:
        unsupported = (
            (ExecutionConfig(allow_short=True), "allow_short=True"),
            (ExecutionConfig(allow_partial_fills=True), "allow_partial_fills=True"),
            (ExecutionConfig(price_source=PriceSource.CLOSE), "price_source=open"),
        )

        for execution, message in unsupported:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    run_backtest(
                        request=self._build_request(execution=execution),
                        bars=self._build_bars(),
                    )

    def test_final_bar_decision_expires_without_out_of_range_fill(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(5)],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 9.0, 8.0, 9.0, 99.0],
                "high": [10.5, 9.5, 8.5, 9.5, 99.5],
                "low": [9.5, 8.5, 7.5, 8.5, 98.5],
                "close": [10.0, 9.0, 8.0, 9.0, 10.0],
                "volume": [1_000.0] * 5,
            }
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=start_ms + (3 * minute),
            end_ms=start_ms + (5 * minute),
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        result = run_backtest(request=request, bars=bars)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.trades, [])
        self.assertEqual(result.diagnostics["tail_expired_delta_count"], 1)
        self.assertEqual(result.equity_curve[-1].equity, 10_000.0)

    def test_event_driven_rejects_multi_symbol_requests(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL", "MSFT"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        with self.assertRaisesRegex(ValueError, "exactly one symbol"):
            run_backtest(request=request, bars=self._build_bars())

    def test_event_driven_rejects_non_bar_requests(self) -> None:
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
            data_granularity=DataGranularity.TICK,
        )

        with self.assertRaisesRegex(ValueError, "event-driven execution"):
            run_backtest(request=request, bars=self._build_bars())

    def _assert_public_execution_results_match(
        self,
        vectorized: BacktestResult,
        event_driven: BacktestResult,
    ) -> None:
        self.assertEqual(vectorized.fills, event_driven.fills)
        self.assertEqual(vectorized.trades, event_driven.trades)
        self.assertEqual(vectorized.equity_curve, event_driven.equity_curve)
        self.assertEqual(vectorized.metrics, event_driven.metrics)
        self.assertEqual(event_driven.diagnostics["engine"], "event_driven")
        for key, value in vectorized.diagnostics.items():
            if key == "engine":
                continue
            self.assertEqual(value, event_driven.diagnostics[key], key)


def _build_enter_and_hold_strategy() -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(),
        target_quantity=1.0,
    )
    return StrategyDefinition(
        strategy_id="enter_hold_fixture",
        feature_specs=("close", "open"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        bar_model=bar_model,
    )


def _build_entry_then_exit_feature_strategy() -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "high"),),
        exit_conditions=(ConditionRule.below("close", "low"),),
        target_quantity=1.0,
    )
    return StrategyDefinition(
        strategy_id="entry_then_exit_fixture",
        feature_specs=("close", "high", "low"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        bar_model=bar_model,
    )


class _RuntimeInvalidAfterBootstrapIndicator:
    def __init__(self) -> None:
        from indicator_engine.core.spec import IndicatorSpec

        self.spec = IndicatorSpec(
            id="runtime_invalid_after_bootstrap_fixture",
            name="Runtime Invalid After Bootstrap Fixture",
            outputs=["value"],
            required_fields=["close"],
            warmup_fn=lambda params: 1,
        )

    def batch(self, data, params):
        from indicator_engine.core.tensor import Tensor

        field_idx = int(np.where(data.fields == "close")[0][0])
        closes = data.data[:, :, field_idx]
        values = np.where(closes >= 20.0, np.nan, 1.0)
        return Tensor(
            data=values[:, :, np.newaxis],
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["value"], dtype=object),
            },
        )


def _register_runtime_invalid_indicator() -> None:
    try:
        from indicator_engine.defaults import get_registry
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[2]
        indicator_engine_path = repo_root / "libs" / "indicator_engine"
        if str(indicator_engine_path) not in sys.path:
            sys.path.append(str(indicator_engine_path))
        from indicator_engine.defaults import get_registry

    registry = get_registry()
    if "runtime_invalid_after_bootstrap_fixture" in registry.list_specs():
        return
    registry.register(_RuntimeInvalidAfterBootstrapIndicator())


def _build_runtime_invalid_feature_strategy() -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("runtime_bad", "close"),),
        exit_conditions=(),
        target_quantity=1.0,
    )
    return StrategyDefinition(
        strategy_id="runtime_invalid_feature_fixture",
        feature_specs=("runtime_bad", "close"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        indicator_requirements=(
            IndicatorFeatureRequirement(
                feature_name="runtime_bad",
                indicator_id="runtime_invalid_after_bootstrap_fixture",
                output_key="value",
            ),
        ),
        bar_model=bar_model,
    )


if __name__ == "__main__":
    unittest.main()
