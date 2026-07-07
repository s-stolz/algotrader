import unittest
from unittest.mock import patch

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import (
    AllowedDirections,
    BacktestEngine,
    OrderSide,
    PriceSource,
    TradeDirection,
)
from domain.types import (
    BacktestRequest,
    ExecutionArrayBundle,
    ExecutionConfig,
    FeatureMatrix,
    SignalMatrix,
    StrategyConfig,
)
from strategies.base import BarStrategyModel, StrategyDefinition
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class TestVectorizedBacktestIntegration(unittest.TestCase):
    def _build_bars(self) -> pd.DataFrame:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
        opens = [10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0]

        return pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": opens,
                "high": [price + 0.5 for price in opens],
                "low": [price - 0.5 for price in opens],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )

    def _build_request(self, execution: ExecutionConfig | None = None) -> BacktestRequest:
        return BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=execution or ExecutionConfig(),
            initial_capital=10_000.0,
        )

    def test_fixture_bars_produce_deterministic_result(self) -> None:
        bars = self._build_bars()
        request = self._build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(
            sorted(result.diagnostics.keys()),
            sorted(
                [
                    "engine",
                    "bars",
                    "symbol",
                    "strategy_id",
                    "fill_timing",
                    "gap_policy",
                    "intrabar_exit_policy",
                    "commission_bps",
                    "slippage_bps",
                    "total_fees",
                    "total_slippage_cost",
                    "stop_loss_exit_count",
                    "take_profit_exit_count",
                    "signal_exit_count",
                    "intrabar_ambiguous_bar_count",
                    "invalid_open_count",
                    "deferred_delta_count",
                    "expired_delta_count",
                    "executed_deferred_count",
                    "tail_expired_delta_count",
                ]
            ),
        )
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].price, 10.0)
        self.assertEqual(result.fills[0].quantity, 1.0)
        self.assertEqual(result.fills[1].price, 13.0)
        self.assertEqual(result.fills[1].quantity, 2.0)
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].realized_pnl, 3.0)
        self.assertEqual(result.equity_curve[-1].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[-1].equity, 10_008.0)
        self.assertAlmostEqual(result.metrics["trade_count"], 1.0)

    def test_request_only_vectorized_run_resolves_strategy_from_registry(self) -> None:
        bars = self._build_bars()
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
        )

        result = run_backtest(request=request, bars=bars)

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(result.diagnostics["strategy_id"], "sma_crossover")
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.equity_curve[-1].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[-1].equity, 10_008.0)

    def test_unknown_request_strategy_id_fails_clearly(self) -> None:
        bars = self._build_bars()
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="not_registered"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

        with self.assertRaisesRegex(ValueError, "Unknown strategy_id 'not_registered'"):
            run_backtest(request=request, bars=bars)

    def test_event_driven_request_dispatches_to_event_driven_engine(self) -> None:
        bars = self._build_bars()
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_180_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            engine=BacktestEngine.EVENT_DRIVEN,
        )

        result = run_backtest(request=request, bars=bars)

        self.assertEqual(result.diagnostics["engine"], "event_driven")
        self.assertEqual(len(result.fills), 2)

    def test_vectorized_engine_does_not_use_row_iterators(self) -> None:
        bars = self._build_bars()
        request = self._build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch.object(pd.DataFrame, "iterrows", side_effect=AssertionError("iterrows called")):
            with patch.object(
                pd.DataFrame,
                "itertuples",
                side_effect=AssertionError("itertuples called"),
            ):
                result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(len(result.fills), 2)

    def test_vectorized_bracket_engine_does_not_call_sequential_strategy_callbacks(self) -> None:
        bars = self._build_bars()
        request = self._build_request()
        strategy = build_sma_crossover_strategy(
            fast_window=2,
            slow_window=3,
            quantity=1.0,
            stop_loss_pct=5.0,
            take_profit_pct=5.0,
        )

        with patch.object(
            BarStrategyModel,
            "evaluate_sequential_signal",
            side_effect=AssertionError("sequential callback called"),
        ):
            with patch.object(
                pd.DataFrame,
                "iterrows",
                side_effect=AssertionError("iterrows called"),
            ):
                with patch.object(
                    pd.DataFrame,
                    "itertuples",
                    side_effect=AssertionError("itertuples called"),
                ):
                    result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(result.diagnostics["engine"], "vectorized")

    def test_non_zero_costs_reduce_post_cost_result(self) -> None:
        bars = self._build_bars()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        zero_cost = run_backtest(
            request=self._build_request(execution=ExecutionConfig()),
            bars=bars,
            strategy=strategy,
        )
        with_cost = run_backtest(
            request=self._build_request(
                execution=ExecutionConfig(
                    commission_bps=20.0,
                    slippage_bps=10.0,
                )
            ),
            bars=bars,
            strategy=strategy,
        )

        self.assertEqual(len(zero_cost.fills), len(with_cost.fills))
        self.assertEqual(len(zero_cost.trades), len(with_cost.trades))
        self.assertGreater(with_cost.diagnostics["total_fees"], 0.0)
        self.assertGreater(with_cost.diagnostics["total_slippage_cost"], 0.0)
        self.assertLess(with_cost.equity_curve[-1].equity, zero_cost.equity_curve[-1].equity)
        self.assertLess(with_cost.trades[0].realized_pnl, zero_cost.trades[0].realized_pnl)

    def test_allow_partial_fills_is_rejected_in_m3_vectorized_baseline(self) -> None:
        bars = self._build_bars()
        request = self._build_request(execution=ExecutionConfig(allow_partial_fills=True))
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaises(ValueError):
            run_backtest(request=request, bars=bars, strategy=strategy)

    def test_price_source_close_is_rejected_in_m3_vectorized_baseline(self) -> None:
        bars = self._build_bars()
        request = self._build_request(execution=ExecutionConfig(price_source=PriceSource.CLOSE))
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaises(ValueError):
            run_backtest(request=request, bars=bars, strategy=strategy)

    def test_request_strategy_id_must_match_strategy_definition(self) -> None:
        bars = self._build_bars()
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="different_strategy"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaises(ValueError):
            run_backtest(request=request, bars=bars, strategy=strategy)

    def test_default_long_and_short_mode_opens_short_from_negative_target(self) -> None:
        bars = self._build_bars()
        strategy = _build_target_quantity_strategy(
            strategy_id="open_short_fixture",
            target=[0.0, -1.0, -1.0, -1.0],
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="open_short_fixture"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].side, OrderSide.SELL)
        self.assertEqual(result.fills[0].quantity, 1.0)
        self.assertEqual(result.fills[0].price, 8.0)
        self.assertEqual(result.trades, [])
        self.assertEqual(result.equity_curve[2].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[-1].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[-1].equity, 10_000.0)

    def test_vectorized_long_only_rejects_negative_signed_targets(self) -> None:
        bars = self._build_bars()
        strategy = _build_target_quantity_strategy(
            strategy_id="invalid_long_only_target_fixture",
            target=[0.0, -1.0, -1.0],
        )
        request = self._build_request(
            execution=ExecutionConfig(allowed_directions=AllowedDirections.LONG_ONLY)
        )
        request = BacktestRequest(
            symbols=request.symbols,
            timeframe=request.timeframe,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            strategy=StrategyConfig(strategy_id=strategy.strategy_id),
            execution=request.execution,
            initial_capital=request.initial_capital,
        )

        with self.assertRaisesRegex(ValueError, "allowed_directions=long_only"):
            run_backtest(request=request, bars=bars, strategy=strategy)

    def test_vectorized_short_only_rejects_positive_signed_targets(self) -> None:
        bars = self._build_bars()
        strategy = _build_target_quantity_strategy(
            strategy_id="invalid_short_only_target_fixture",
            target=[0.0, 1.0, 1.0],
        )
        request = self._build_request(
            execution=ExecutionConfig(allowed_directions=AllowedDirections.SHORT_ONLY)
        )
        request = BacktestRequest(
            symbols=request.symbols,
            timeframe=request.timeframe,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            strategy=StrategyConfig(strategy_id=strategy.strategy_id),
            execution=request.execution,
            initial_capital=request.initial_capital,
        )

        with self.assertRaisesRegex(ValueError, "allowed_directions=short_only"):
            run_backtest(request=request, bars=bars, strategy=strategy)

    def test_buy_fills_reduce_and_cover_short_positions(self) -> None:
        bars = self._build_bars()
        strategy = _build_target_quantity_strategy(
            strategy_id="short_reduce_cover_fixture",
            target=[0.0, -2.0, -1.0, 0.0, 0.0],
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id=strategy.strategy_id),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(
            [(fill.side, fill.quantity, fill.price) for fill in result.fills],
            [
                (OrderSide.SELL, 2.0, 8.0),
                (OrderSide.BUY, 1.0, 9.0),
                (OrderSide.BUY, 1.0, 10.0),
            ],
        )
        self.assertEqual(result.equity_curve[2].positions, {"AAPL": -2.0})
        self.assertEqual(result.equity_curve[3].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[4].positions, {})
        self.assertEqual(
            [
                (trade.trade_direction, trade.quantity, trade.realized_pnl)
                for trade in result.trades
            ],
            [
                (TradeDirection.SHORT, 1.0, -1.0),
                (TradeDirection.SHORT, 1.0, -2.0),
            ],
        )

    def test_direct_direction_flips_execute_as_single_delta_fills(self) -> None:
        bars = self._build_bars()
        strategy = _build_target_quantity_strategy(
            strategy_id="direct_flip_fixture",
            target=[0.0, 1.0, -1.0, 1.0, 1.0],
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id=strategy.strategy_id),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual(
            [(fill.side, fill.quantity, fill.price) for fill in result.fills],
            [
                (OrderSide.BUY, 1.0, 8.0),
                (OrderSide.SELL, 2.0, 9.0),
                (OrderSide.BUY, 2.0, 10.0),
            ],
        )
        self.assertEqual(result.equity_curve[2].positions, {"AAPL": 1.0})
        self.assertEqual(result.equity_curve[3].positions, {"AAPL": -1.0})
        self.assertEqual(result.equity_curve[4].positions, {"AAPL": 1.0})
        self.assertEqual(
            [
                (trade.trade_direction, trade.quantity, trade.realized_pnl)
                for trade in result.trades
            ],
            [
                (TradeDirection.LONG, 1.0, 1.0),
                (TradeDirection.SHORT, 1.0, -1.0),
            ],
        )

    def test_short_entries_and_covers_apply_side_based_costs(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * idx for idx in range(4)],
                "symbol": ["AAPL"] * 4,
                "open": [100.0, 100.0, 100.0, 100.0],
                "high": [101.0, 101.0, 101.0, 101.0],
                "low": [99.0, 99.0, 99.0, 99.0],
                "close": [100.0, 100.0, 100.0, 100.0],
                "volume": [1_000.0] * 4,
            }
        )
        strategy = _build_target_quantity_strategy(
            strategy_id="short_cost_fixture",
            target=[0.0, -1.0, 0.0, 0.0],
        )
        request = BacktestRequest(
            symbols=["AAPL"],
            timeframe="1m",
            start_ms=start_ms,
            end_ms=start_ms + (4 * minute),
            strategy=StrategyConfig(strategy_id=strategy.strategy_id),
            execution=ExecutionConfig(commission_bps=20.0, slippage_bps=10.0),
            initial_capital=10_000.0,
        )

        result = run_backtest(request=request, bars=bars, strategy=strategy)

        self.assertEqual([fill.side for fill in result.fills], [OrderSide.SELL, OrderSide.BUY])
        self.assertAlmostEqual(result.fills[0].price, 99.9)
        self.assertAlmostEqual(result.fills[0].fees, 0.1998)
        self.assertAlmostEqual(result.fills[1].price, 100.1)
        self.assertAlmostEqual(result.fills[1].fees, 0.2002)
        self.assertAlmostEqual(result.diagnostics["total_slippage_cost"], 0.2)
        self.assertAlmostEqual(result.diagnostics["total_fees"], 0.4)
        self.assertAlmostEqual(result.trades[0].realized_pnl, -0.6)
        self.assertAlmostEqual(result.equity_curve[-1].equity, 9_999.4)


def _build_target_quantity_strategy(
    *,
    strategy_id: str,
    target: list[float],
) -> StrategyDefinition:
    def decision_model(features: FeatureMatrix) -> SignalMatrix:
        return SignalMatrix(
            timestamp_ms=features.timestamp_ms,
            signals_by_symbol={"AAPL": [0] * len(features.timestamp_ms)},
        )

    def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
        count = len(signals.timestamp_ms)
        values = [float(value) for value in target[:count]]
        if len(values) < count:
            values.extend([float(target[-1])] * (count - len(values)))
        return ExecutionArrayBundle(
            timestamp_ms=signals.timestamp_ms,
            target_quantity_by_symbol={"AAPL": values},
        )

    return StrategyDefinition(
        strategy_id=strategy_id,
        feature_specs=(),
        decision_model=decision_model,
        position_builder=position_builder,
    )


if __name__ == "__main__":
    unittest.main()
