import unittest

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import (
    AllowedDirections,
    BacktestEngine,
    DataGranularity,
    ExitReason,
    GapPolicy,
    IntrabarExitPolicy,
    OrderSide,
    TradeDirection,
)
from domain.types import (
    BacktestRequest,
    ExecutionArrayBundle,
    ExecutionConfig,
    StrategyConfig,
)
from strategies.base import BarStrategyModel, ProtectiveExitSpec, StrategyDefinition
from strategies.conditions import ConditionRule


class TestBacktestEngineParity(unittest.TestCase):
    def _build_sma_bars(self) -> pd.DataFrame:
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

    def _build_sma_request(
        self,
        *,
        engine: BacktestEngine,
        execution: ExecutionConfig | None = None,
        symbols: list[str] | None = None,
        data_granularity: DataGranularity = DataGranularity.BAR,
    ) -> BacktestRequest:
        start_ms = 1_700_000_000_000
        minute = 60_000
        return BacktestRequest(
            symbols=symbols or ["AAPL"],
            timeframe="1m",
            start_ms=start_ms + (3 * minute),
            end_ms=start_ms + (9 * 60_000),
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=execution or ExecutionConfig(),
            initial_capital=10_000.0,
            engine=engine,
            data_granularity=data_granularity,
        )

    def test_sma_crossover_public_results_match_across_supported_engines(self) -> None:
        bars = self._build_sma_bars()
        executions = (
            ExecutionConfig(),
            ExecutionConfig(commission_bps=20.0, slippage_bps=10.0),
        )

        for execution in executions:
            with self.subTest(execution=execution):
                vectorized = run_backtest(
                    request=self._build_sma_request(
                        engine=BacktestEngine.VECTORIZED,
                        execution=execution,
                    ),
                    bars=bars,
                )
                event_driven = run_backtest(
                    request=self._build_sma_request(
                        engine=BacktestEngine.EVENT_DRIVEN,
                        execution=execution,
                    ),
                    bars=bars,
                )

                self.assertGreater(len(vectorized.fills), 0)
                self._assert_public_results_match(vectorized, event_driven)

    def test_next_open_timing_trap_matches_without_same_bar_fill(self) -> None:
        bars = self._build_sma_bars()

        vectorized = run_backtest(
            request=self._build_sma_request(engine=BacktestEngine.VECTORIZED),
            bars=bars,
        )
        event_driven = run_backtest(
            request=self._build_sma_request(engine=BacktestEngine.EVENT_DRIVEN),
            bars=bars,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [(fill.timestamp_ms, fill.price) for fill in event_driven.fills],
            [
                (1_700_000_300_000, 10.0),
                (1_700_000_480_000, 13.0),
            ],
        )
        self.assertNotIn(99.0, [fill.price for fill in event_driven.fills])

    def test_completed_bar_decision_does_not_use_future_feature_values(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(5)],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 77.0, 12.0, 13.0, 14.0],
                "high": [10.5, 78.0, 12.5, 13.5, 14.5],
                "low": [8.5, 9.5, 11.5, 12.5, 13.5],
                "close": [9.0, 78.0, 12.0, 13.0, 14.0],
                "volume": [1_000.0] * 5,
            }
        )
        strategy = _build_close_above_open_strategy()

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (5 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (5 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(len(event_driven.fills), 1)
        self.assertEqual(event_driven.fills[0].timestamp_ms, start_ms + (2 * minute))
        self.assertEqual(event_driven.fills[0].price, 12.0)

    def test_final_bar_decision_expires_without_out_of_window_open(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(5)],
                "symbol": ["AAPL"] * 5,
                "open": [10.0, 10.0, 10.0, 11.0, 99.0],
                "high": [10.5, 10.5, 10.5, 12.5, 100.0],
                "low": [8.5, 8.5, 8.5, 10.5, 98.0],
                "close": [9.0, 9.0, 9.0, 12.0, 100.0],
                "volume": [1_000.0] * 5,
            }
        )
        strategy = _build_close_above_open_strategy()
        end_ms = start_ms + (4 * minute)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=end_ms,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=end_ms,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills, [])
        self.assertEqual(event_driven.trades, [])
        self.assertEqual(event_driven.diagnostics["tail_expired_delta_count"], 1)
        self.assertEqual(
            [snapshot.timestamp_ms for snapshot in event_driven.equity_curve],
            [start_ms + minute * i for i in range(4)],
        )

    def test_signal_exit_diagnostics_count_short_covers_not_short_entries(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_ohlc_bars(
            start_ms=start_ms,
            minute=minute,
            opens=(100.0, 99.0, 98.0, 97.0),
            highs=(101.0, 100.0, 99.0, 98.0),
            lows=(99.0, 98.0, 97.0, 96.0),
            closes=(101.0, 100.0, 99.0, 98.0),
        )
        open_short_strategy = _build_timestamp_target_strategy(
            strategy_id="open_short_diagnostics_fixture",
            target_by_timestamp={
                start_ms: -1.0,
                start_ms + minute: -1.0,
                start_ms + (2 * minute): -1.0,
                start_ms + (3 * minute): -1.0,
            },
        )
        reduce_and_cover_strategy = _build_timestamp_target_strategy(
            strategy_id="short_cover_diagnostics_fixture",
            target_by_timestamp={
                start_ms: -2.0,
                start_ms + minute: -1.0,
                start_ms + (2 * minute): 0.0,
                start_ms + (3 * minute): 0.0,
            },
        )

        cases = (
            (open_short_strategy, 0),
            (reduce_and_cover_strategy, 2),
        )
        for strategy, expected_exit_count in cases:
            for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
                with self.subTest(strategy=strategy.strategy_id, engine=engine):
                    result = run_backtest(
                        request=_build_request_for_strategy(
                            engine=engine,
                            strategy=strategy,
                            start_ms=start_ms,
                            end_ms=start_ms + (4 * minute),
                        ),
                        bars=bars,
                        strategy=strategy,
                    )

                    self.assertEqual(
                        result.diagnostics["signal_exit_count"],
                        expected_exit_count,
                    )

    def test_stop_loss_is_active_on_entry_bar_and_takes_priority_over_signal_exit(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(3)],
                "symbol": ["AAPL"] * 3,
                "open": [99.0, 100.0, 88.0],
                "high": [101.0, 101.0, 89.0],
                "low": [98.0, 94.0, 87.0],
                "close": [100.0, 90.0, 88.0],
                "volume": [1_000.0] * 3,
            }
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0)
        execution = ExecutionConfig(allowed_directions=AllowedDirections.LONG_ONLY)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [(fill.timestamp_ms, fill.side, fill.price) for fill in event_driven.fills],
            [
                (start_ms + minute, OrderSide.BUY, 100.0),
                (start_ms + minute, OrderSide.SELL, 95.0),
            ],
        )
        self.assertEqual(len(event_driven.trades), 1)
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)

    def test_gap_through_stop_loss_fills_at_bar_open_across_engines(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(4)],
                "symbol": ["AAPL"] * 4,
                "open": [99.0, 100.0, 93.0, 96.0],
                "high": [101.0, 101.0, 94.0, 97.0],
                "low": [98.0, 96.0, 92.0, 95.0],
                "close": [100.0, 100.0, 93.0, 96.0],
                "volume": [1_000.0] * 4,
            }
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [(fill.timestamp_ms, fill.side, fill.price) for fill in event_driven.fills],
            [
                (start_ms + minute, OrderSide.BUY, 100.0),
                (start_ms + (2 * minute), OrderSide.SELL, 93.0),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)

    def test_gap_through_stop_loss_keeps_priority_over_pending_signal_exit(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(4)],
                "symbol": ["AAPL"] * 4,
                "open": [99.0, 100.0, 93.0, 96.0],
                "high": [101.0, 101.0, 94.0, 97.0],
                "low": [98.0, 96.0, 92.0, 95.0],
                "close": [100.0, 96.0, 93.0, 96.0],
                "volume": [1_000.0] * 4,
            }
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [
                (fill.timestamp_ms, fill.side, fill.price, fill.exit_reason)
                for fill in event_driven.fills
            ],
            [
                (start_ms + minute, OrderSide.BUY, 100.0, None),
                (start_ms + (2 * minute), OrderSide.SELL, 93.0, ExitReason.STOP_LOSS),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)

    def test_take_profit_is_active_on_entry_bar_and_takes_priority_over_signal_exit(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(3)],
                "symbol": ["AAPL"] * 3,
                "open": [99.0, 100.0, 108.0],
                "high": [101.0, 106.0, 109.0],
                "low": [98.0, 99.0, 107.0],
                "close": [100.0, 90.0, 108.0],
                "volume": [1_000.0] * 3,
            }
        )
        strategy = _build_price_action_strategy(take_profit_pct=5.0)
        execution = ExecutionConfig(allowed_directions=AllowedDirections.LONG_ONLY)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [
                (fill.timestamp_ms, fill.side, fill.price, fill.exit_reason)
                for fill in event_driven.fills
            ],
            [
                (start_ms + minute, OrderSide.BUY, 100.0, None),
                (start_ms + minute, OrderSide.SELL, 105.0, ExitReason.TAKE_PROFIT),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.TAKE_PROFIT)

    def test_gap_through_take_profit_fills_at_bar_open_across_engines(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(4)],
                "symbol": ["AAPL"] * 4,
                "open": [99.0, 100.0, 107.0, 106.0],
                "high": [101.0, 101.0, 108.0, 107.0],
                "low": [98.0, 99.0, 106.0, 105.0],
                "close": [100.0, 100.0, 107.0, 106.0],
                "volume": [1_000.0] * 4,
            }
        )
        strategy = _build_price_action_strategy(take_profit_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [(fill.timestamp_ms, fill.side, fill.price) for fill in event_driven.fills],
            [
                (start_ms + minute, OrderSide.BUY, 100.0),
                (start_ms + (2 * minute), OrderSide.SELL, 107.0),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.TAKE_PROFIT)

    def test_gap_through_take_profit_keeps_priority_over_pending_signal_exit(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * i for i in range(4)],
                "symbol": ["AAPL"] * 4,
                "open": [99.0, 100.0, 107.0, 106.0],
                "high": [101.0, 101.0, 108.0, 107.0],
                "low": [98.0, 96.0, 106.0, 105.0],
                "close": [100.0, 96.0, 107.0, 106.0],
                "volume": [1_000.0] * 4,
            }
        )
        strategy = _build_price_action_strategy(take_profit_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (4 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [
                (fill.timestamp_ms, fill.side, fill.price, fill.exit_reason)
                for fill in event_driven.fills
            ],
            [
                (start_ms + minute, OrderSide.BUY, 100.0, None),
                (start_ms + (2 * minute), OrderSide.SELL, 107.0, ExitReason.TAKE_PROFIT),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.TAKE_PROFIT)

    def test_default_conservative_policy_chooses_stop_loss_on_ambiguous_bar(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_combined_bracket_ambiguous_bars(start_ms=start_ms, minute=minute)
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [
                (fill.timestamp_ms, fill.side, fill.price, fill.exit_reason)
                for fill in event_driven.fills
            ],
            [
                (start_ms + minute, OrderSide.BUY, 100.0, None),
                (start_ms + minute, OrderSide.SELL, 95.0, ExitReason.STOP_LOSS),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)
        self.assertEqual(event_driven.diagnostics["intrabar_exit_policy"], "conservative")
        self.assertEqual(event_driven.diagnostics["stop_loss_exit_count"], 1)
        self.assertEqual(event_driven.diagnostics["take_profit_exit_count"], 0)
        self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)
        self.assertEqual(event_driven.diagnostics["intrabar_ambiguous_bar_count"], 1)

    def test_explicit_stop_first_policy_chooses_stop_loss_on_ambiguous_bar(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_combined_bracket_ambiguous_bars(start_ms=start_ms, minute=minute)
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)
        execution = ExecutionConfig(intrabar_exit_policy=IntrabarExitPolicy.STOP_FIRST)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills[1].price, 95.0)
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)
        self.assertEqual(event_driven.diagnostics["intrabar_exit_policy"], "stop_first")
        self.assertEqual(event_driven.diagnostics["intrabar_ambiguous_bar_count"], 1)

    def test_take_profit_first_policy_chooses_take_profit_on_ambiguous_bar(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_combined_bracket_ambiguous_bars(start_ms=start_ms, minute=minute)
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)
        execution = ExecutionConfig(intrabar_exit_policy=IntrabarExitPolicy.TAKE_PROFIT_FIRST)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills[1].price, 105.0)
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.TAKE_PROFIT)
        self.assertEqual(event_driven.diagnostics["intrabar_exit_policy"], "take_profit_first")
        self.assertEqual(event_driven.diagnostics["stop_loss_exit_count"], 0)
        self.assertEqual(event_driven.diagnostics["take_profit_exit_count"], 1)
        self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)
        self.assertEqual(event_driven.diagnostics["intrabar_ambiguous_bar_count"], 1)

    def test_signal_exit_keeps_planned_protective_prices_across_engines(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_ohlc_bars(
            start_ms=start_ms,
            minute=minute,
            opens=(99.0, 100.0, 102.0),
            highs=(101.0, 103.0, 103.0),
            lows=(98.0, 98.0, 101.0),
            closes=(100.0, 99.0, 102.0),
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=10.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(len(event_driven.trades), 1)
        trade = event_driven.trades[0]
        self.assertEqual(trade.exit_reason, ExitReason.SIGNAL)
        self.assertEqual(trade.exit_price, 102.0)
        self.assertAlmostEqual(trade.stop_loss_price or 0.0, 95.0)
        self.assertAlmostEqual(trade.take_profit_price or 0.0, 110.0)

    def test_error_policy_rejects_ambiguous_combined_bracket_bar(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_combined_bracket_ambiguous_bars(start_ms=start_ms, minute=minute)
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)
        execution = ExecutionConfig(intrabar_exit_policy=IntrabarExitPolicy.ERROR)

        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine):
                with self.assertRaisesRegex(ValueError, "Ambiguous intrabar protective exit"):
                    run_backtest(
                        request=_build_request_for_strategy(
                            engine=engine,
                            strategy=strategy,
                            start_ms=start_ms,
                            end_ms=start_ms + (3 * minute),
                            execution=execution,
                        ),
                        bars=bars,
                        strategy=strategy,
                    )

    def test_bracket_parity_matrix_applies_costs_to_protective_exits(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        execution = ExecutionConfig(commission_bps=20.0, slippage_bps=10.0)
        cases = (
            (
                "stop_only",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 96.0),
                    highs=(101.0, 101.0, 97.0),
                    lows=(98.0, 94.0, 95.0),
                    closes=(100.0, 100.0, 96.0),
                ),
                _build_price_action_strategy(stop_loss_pct=5.0),
                ExitReason.STOP_LOSS,
                1,
                0,
                0,
                95.095,
                None,
            ),
            (
                "target_only",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 106.0),
                    highs=(101.0, 106.0, 107.0),
                    lows=(98.0, 99.0, 105.0),
                    closes=(100.0, 100.0, 106.0),
                ),
                _build_price_action_strategy(take_profit_pct=5.0),
                ExitReason.TAKE_PROFIT,
                0,
                1,
                0,
                None,
                105.105,
            ),
            (
                "combined_default_ambiguous",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 100.0),
                    highs=(101.0, 106.5, 101.0),
                    lows=(98.0, 94.0, 99.0),
                    closes=(100.0, 100.0, 100.0),
                ),
                _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0),
                ExitReason.STOP_LOSS,
                1,
                0,
                1,
                95.095,
                105.105,
            ),
        )

        for (
            name,
            bars,
            strategy,
            exit_reason,
            stop_count,
            target_count,
            ambiguous_count,
            expected_stop_price,
            expected_target_price,
        ) in cases:
            with self.subTest(name=name):
                vectorized = run_backtest(
                    request=_build_request_for_strategy(
                        engine=BacktestEngine.VECTORIZED,
                        strategy=strategy,
                        start_ms=start_ms,
                        end_ms=start_ms + (3 * minute),
                        execution=execution,
                    ),
                    bars=bars,
                    strategy=strategy,
                )
                event_driven = run_backtest(
                    request=_build_request_for_strategy(
                        engine=BacktestEngine.EVENT_DRIVEN,
                        strategy=strategy,
                        start_ms=start_ms,
                        end_ms=start_ms + (3 * minute),
                        execution=execution,
                    ),
                    bars=bars,
                    strategy=strategy,
                )

                self._assert_public_results_match(vectorized, event_driven)
                self.assertEqual(len(event_driven.trades), 1)
                trade = event_driven.trades[0]
                self.assertEqual(trade.exit_reason, exit_reason)
                if expected_stop_price is None:
                    self.assertIsNone(trade.stop_loss_price)
                else:
                    self.assertAlmostEqual(trade.stop_loss_price or 0.0, expected_stop_price)
                if expected_target_price is None:
                    self.assertIsNone(trade.take_profit_price)
                else:
                    self.assertAlmostEqual(
                        trade.take_profit_price or 0.0,
                        expected_target_price,
                    )
                self.assertEqual(event_driven.fills[-1].exit_reason, exit_reason)
                self.assertGreater(event_driven.fills[-1].fees, 0.0)
                self.assertGreater(event_driven.diagnostics["total_fees"], 0.0)
                self.assertGreater(event_driven.diagnostics["total_slippage_cost"], 0.0)
                self.assertEqual(event_driven.diagnostics["stop_loss_exit_count"], stop_count)
                self.assertEqual(event_driven.diagnostics["take_profit_exit_count"], target_count)
                self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)
                self.assertEqual(
                    event_driven.diagnostics["intrabar_ambiguous_bar_count"],
                    ambiguous_count,
                )

    def test_final_bar_bracket_entry_signal_expires_without_out_of_window_open(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_ohlc_bars(
            start_ms=start_ms,
            minute=minute,
            opens=(100.0, 100.0, 99.0),
            highs=(101.0, 101.0, 150.0),
            lows=(99.0, 99.0, 50.0),
            closes=(100.0, 100.0, 100.0),
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills, [])
        self.assertEqual(event_driven.trades, [])
        self.assertEqual(event_driven.diagnostics["tail_expired_delta_count"], 1)
        self.assertEqual(event_driven.diagnostics["stop_loss_exit_count"], 0)
        self.assertEqual(event_driven.diagnostics["take_profit_exit_count"], 0)

    def test_final_bar_protective_exit_executes_without_future_open(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_ohlc_bars(
            start_ms=start_ms,
            minute=minute,
            opens=(99.0, 100.0, 100.0),
            highs=(101.0, 101.0, 101.0),
            lows=(98.0, 99.0, 94.0),
            closes=(100.0, 100.0, 90.0),
        )
        strategy = _build_price_action_strategy(stop_loss_pct=5.0)
        execution = ExecutionConfig(allowed_directions=AllowedDirections.LONG_ONLY)

        vectorized = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.VECTORIZED,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )
        event_driven = run_backtest(
            request=_build_request_for_strategy(
                engine=BacktestEngine.EVENT_DRIVEN,
                strategy=strategy,
                start_ms=start_ms,
                end_ms=start_ms + (3 * minute),
                execution=execution,
            ),
            bars=bars,
            strategy=strategy,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(
            [
                (fill.timestamp_ms, fill.side, fill.price, fill.exit_reason)
                for fill in event_driven.fills
            ],
            [
                (start_ms + minute, OrderSide.BUY, 100.0, None),
                (start_ms + (2 * minute), OrderSide.SELL, 95.0, ExitReason.STOP_LOSS),
            ],
        )
        self.assertEqual(event_driven.trades[0].exit_reason, ExitReason.STOP_LOSS)
        self.assertEqual(event_driven.diagnostics["tail_expired_delta_count"], 0)
        self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)

    def test_short_protective_exits_match_across_engines(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        cases = (
            (
                "stop_loss_entry_bar",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 100.0),
                    highs=(101.0, 106.0, 101.0),
                    lows=(98.0, 99.0, 99.0),
                    closes=(100.0, 100.0, 100.0),
                ),
                ExecutionConfig(),
                ExitReason.STOP_LOSS,
                105.0,
                1,
                0,
                0,
            ),
            (
                "take_profit_entry_bar",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 100.0),
                    highs=(101.0, 101.0, 101.0),
                    lows=(98.0, 94.0, 99.0),
                    closes=(100.0, 100.0, 100.0),
                ),
                ExecutionConfig(),
                ExitReason.TAKE_PROFIT,
                95.0,
                0,
                1,
                0,
            ),
            (
                "gap_through_stop_loss",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 107.0),
                    highs=(101.0, 101.0, 108.0),
                    lows=(98.0, 99.0, 106.0),
                    closes=(100.0, 100.0, 107.0),
                ),
                ExecutionConfig(),
                ExitReason.STOP_LOSS,
                107.0,
                1,
                0,
                0,
            ),
            (
                "gap_through_take_profit",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 93.0),
                    highs=(101.0, 101.0, 94.0),
                    lows=(98.0, 99.0, 92.0),
                    closes=(100.0, 100.0, 93.0),
                ),
                ExecutionConfig(),
                ExitReason.TAKE_PROFIT,
                93.0,
                0,
                1,
                0,
            ),
            (
                "ambiguous_conservative",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 100.0),
                    highs=(101.0, 106.0, 101.0),
                    lows=(98.0, 94.0, 99.0),
                    closes=(100.0, 100.0, 100.0),
                ),
                ExecutionConfig(),
                ExitReason.STOP_LOSS,
                105.0,
                1,
                0,
                1,
            ),
            (
                "ambiguous_take_profit_first",
                _build_ohlc_bars(
                    start_ms=start_ms,
                    minute=minute,
                    opens=(99.0, 100.0, 100.0),
                    highs=(101.0, 106.0, 101.0),
                    lows=(98.0, 94.0, 99.0),
                    closes=(100.0, 100.0, 100.0),
                ),
                ExecutionConfig(intrabar_exit_policy=IntrabarExitPolicy.TAKE_PROFIT_FIRST),
                ExitReason.TAKE_PROFIT,
                95.0,
                0,
                1,
                1,
            ),
        )
        strategy = _build_short_price_action_strategy(stop_loss_pct=5.0, take_profit_pct=5.0)

        for (
            name,
            bars,
            execution,
            exit_reason,
            exit_price,
            stop_count,
            target_count,
            ambiguous_count,
        ) in cases:
            with self.subTest(name=name):
                vectorized = run_backtest(
                    request=_build_request_for_strategy(
                        engine=BacktestEngine.VECTORIZED,
                        strategy=strategy,
                        start_ms=start_ms,
                        end_ms=start_ms + (3 * minute),
                        execution=execution,
                    ),
                    bars=bars,
                    strategy=strategy,
                )
                event_driven = run_backtest(
                    request=_build_request_for_strategy(
                        engine=BacktestEngine.EVENT_DRIVEN,
                        strategy=strategy,
                        start_ms=start_ms,
                        end_ms=start_ms + (3 * minute),
                        execution=execution,
                    ),
                    bars=bars,
                    strategy=strategy,
                )

                self._assert_public_results_match(vectorized, event_driven)
                self.assertEqual(
                    [(fill.side, fill.price, fill.exit_reason) for fill in event_driven.fills],
                    [
                        (OrderSide.SELL, 100.0, None),
                        (OrderSide.BUY, exit_price, exit_reason),
                    ],
                )
                self.assertEqual(len(event_driven.trades), 1)
                trade = event_driven.trades[0]
                self.assertEqual(trade.trade_direction, TradeDirection.SHORT)
                self.assertEqual(trade.exit_reason, exit_reason)
                self.assertEqual(trade.stop_loss_price, 105.0)
                self.assertEqual(trade.take_profit_price, 95.0)
                self.assertEqual(event_driven.diagnostics["stop_loss_exit_count"], stop_count)
                self.assertEqual(event_driven.diagnostics["take_profit_exit_count"], target_count)
                self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)
                self.assertEqual(
                    event_driven.diagnostics["intrabar_ambiguous_bar_count"],
                    ambiguous_count,
                )

    def test_both_engines_reject_negative_strategy_outputs_in_long_only_mode(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        bars = _build_ohlc_bars(
            start_ms=start_ms,
            minute=minute,
            opens=(99.0, 100.0, 100.0),
            highs=(101.0, 101.0, 101.0),
            lows=(98.0, 99.0, 99.0),
            closes=(100.0, 100.0, 100.0),
        )
        negative_target_strategy = _build_short_like_target_strategy()
        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine, invalid="negative_target"):
                with self.assertRaisesRegex(ValueError, "long[-_]only"):
                    run_backtest(
                        request=_build_request_for_strategy(
                            engine=engine,
                            strategy=negative_target_strategy,
                            start_ms=start_ms,
                            end_ms=start_ms + (3 * minute),
                            execution=ExecutionConfig(
                                allowed_directions=AllowedDirections.LONG_ONLY
                            ),
                        ),
                        bars=bars,
                        strategy=negative_target_strategy,
                    )

    def test_short_only_sma_flat_exit_while_flat_emits_no_execution_artifacts(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * index for index in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": closes,
                "high": [price + 0.5 for price in closes],
                "low": [price - 0.5 for price in closes],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )
        execution = ExecutionConfig(allowed_directions=AllowedDirections.SHORT_ONLY)

        vectorized = run_backtest(
            request=self._build_sma_request(
                engine=BacktestEngine.VECTORIZED,
                execution=execution,
            ),
            bars=bars,
        )
        event_driven = run_backtest(
            request=self._build_sma_request(
                engine=BacktestEngine.EVENT_DRIVEN,
                execution=execution,
            ),
            bars=bars,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills, [])
        self.assertEqual(event_driven.trades, [])
        self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)

    def test_short_only_sma_flat_exit_after_expired_entry_stays_flat(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        closes = [10.0, 11.0, 12.0, 11.0, 10.0, 9.0, 10.0, 11.0, 12.0, 13.0]
        opens = [10.0, 11.0, 12.0, 11.0, 10.0, 0.0, 10.0, 11.0, 12.0, 13.0]
        bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms + minute * index for index in range(len(closes))],
                "symbol": ["AAPL"] * len(closes),
                "open": opens,
                "high": [max(open_price, close) + 0.5 for open_price, close in zip(opens, closes)],
                "low": [min(open_price, close) - 0.5 for open_price, close in zip(opens, closes)],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            }
        )
        execution = ExecutionConfig(
            allowed_directions=AllowedDirections.SHORT_ONLY,
            gap_policy=GapPolicy.EXPIRE,
        )

        vectorized = run_backtest(
            request=self._build_sma_request(
                engine=BacktestEngine.VECTORIZED,
                execution=execution,
            ),
            bars=bars,
        )
        event_driven = run_backtest(
            request=self._build_sma_request(
                engine=BacktestEngine.EVENT_DRIVEN,
                execution=execution,
            ),
            bars=bars,
        )

        self._assert_public_results_match(vectorized, event_driven)
        self.assertEqual(event_driven.fills, [])
        self.assertEqual(event_driven.trades, [])
        self.assertEqual(event_driven.equity_curve[-1].positions, {})
        self.assertEqual(event_driven.diagnostics["expired_delta_count"], 1)
        self.assertEqual(event_driven.diagnostics["signal_exit_count"], 0)

    def test_both_engines_reject_multi_symbol_and_non_bar_requests(self) -> None:
        bars = self._build_sma_bars()

        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine, invalid="multi-symbol"):
                with self.assertRaisesRegex(ValueError, "exactly one symbol"):
                    run_backtest(
                        request=self._build_sma_request(
                            engine=engine,
                            symbols=["AAPL", "MSFT"],
                        ),
                        bars=bars,
                    )

            with self.subTest(engine=engine, invalid="data-granularity"):
                with self.assertRaisesRegex(ValueError, "Unsupported data_granularity 'tick'"):
                    run_backtest(
                        request=self._build_sma_request(
                            engine=engine,
                            data_granularity=DataGranularity.TICK,
                        ),
                        bars=bars,
                    )

    def _assert_public_results_match(self, vectorized, event_driven) -> None:
        self.assertEqual(vectorized.fills, event_driven.fills)
        self.assertEqual(vectorized.trades, event_driven.trades)
        self.assertEqual(vectorized.equity_curve, event_driven.equity_curve)
        self.assertEqual(vectorized.metrics, event_driven.metrics)

        self.assertEqual(vectorized.request.strategy, event_driven.request.strategy)
        self.assertEqual(vectorized.request.symbols, event_driven.request.symbols)
        self.assertEqual(vectorized.request.timeframe, event_driven.request.timeframe)
        self.assertEqual(vectorized.request.start_ms, event_driven.request.start_ms)
        self.assertEqual(vectorized.request.end_ms, event_driven.request.end_ms)
        self.assertEqual(vectorized.request.execution, event_driven.request.execution)
        self.assertEqual(vectorized.request.initial_capital, event_driven.request.initial_capital)
        self.assertEqual(vectorized.request.engine, BacktestEngine.VECTORIZED)
        self.assertEqual(event_driven.request.engine, BacktestEngine.EVENT_DRIVEN)

        self.assertEqual(vectorized.diagnostics["engine"], "vectorized")
        self.assertEqual(event_driven.diagnostics["engine"], "event_driven")
        for key, value in vectorized.diagnostics.items():
            if key == "engine":
                continue
            self.assertEqual(value, event_driven.diagnostics[key], key)


def _build_close_above_open_strategy() -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(),
        target_quantity=1.0,
    )
    return StrategyDefinition(
        strategy_id="close_above_open_fixture",
        feature_specs=("close", "open"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        bar_model=bar_model,
    )


def _build_timestamp_target_strategy(
    *,
    strategy_id: str,
    target_by_timestamp: dict[int, float],
) -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(),
        target_quantity=1.0,
    )

    def apply_targets(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
        return ExecutionArrayBundle(
            timestamp_ms=bundle.timestamp_ms,
            target_quantity_by_symbol={
                symbol: [
                    float(target_by_timestamp.get(int(timestamp_ms), 0.0))
                    for timestamp_ms in bundle.timestamp_ms
                ]
                for symbol in bundle.target_quantity_by_symbol
            },
        )

    return StrategyDefinition(
        strategy_id=strategy_id,
        feature_specs=("close", "open"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        risk_rules=(apply_targets,),
        bar_model=bar_model,
    )


def _build_price_action_strategy(
    *,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(ConditionRule.below("close", "open"),),
        target_quantity=1.0,
        protective_exit=ProtectiveExitSpec(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        ),
    )
    return StrategyDefinition(
        strategy_id="price_action_fixture",
        feature_specs=("close", "open"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        bar_model=bar_model,
    )


def _build_short_price_action_strategy(
    *,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> StrategyDefinition:
    base = _build_price_action_strategy(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )

    def force_short_targets(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
        return ExecutionArrayBundle(
            timestamp_ms=bundle.timestamp_ms,
            target_quantity_by_symbol={
                symbol: [
                    -abs(float(quantity)) if float(quantity) > 0.0 else float(quantity)
                    for quantity in quantities
                ]
                for symbol, quantities in bundle.target_quantity_by_symbol.items()
            },
        )

    return StrategyDefinition(
        strategy_id="short_price_action_fixture",
        feature_specs=base.feature_specs,
        decision_model=base.decision_model,
        position_builder=base.position_builder,
        risk_rules=(force_short_targets,),
        bar_model=base.bar_model,
    )


def _build_combined_bracket_ambiguous_bars(*, start_ms: int, minute: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ms": [start_ms + minute * i for i in range(3)],
            "symbol": ["AAPL"] * 3,
            "open": [99.0, 100.0, 100.0],
            "high": [101.0, 106.0, 101.0],
            "low": [98.0, 94.0, 99.0],
            "close": [100.0, 100.0, 100.0],
            "volume": [1_000.0] * 3,
        }
    )


def _build_ohlc_bars(
    *,
    start_ms: int,
    minute: int,
    opens: tuple[float, ...],
    highs: tuple[float, ...],
    lows: tuple[float, ...],
    closes: tuple[float, ...],
) -> pd.DataFrame:
    row_count = len(opens)
    return pd.DataFrame(
        {
            "timestamp_ms": [start_ms + minute * i for i in range(row_count)],
            "symbol": ["AAPL"] * row_count,
            "open": list(opens),
            "high": list(highs),
            "low": list(lows),
            "close": list(closes),
            "volume": [1_000.0] * row_count,
        }
    )


def _build_short_like_target_strategy() -> StrategyDefinition:
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(),
        target_quantity=1.0,
        protective_exit=ProtectiveExitSpec(stop_loss_pct=5.0),
    )

    def force_short_target(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
        target = [
            -abs(float(quantity)) if float(quantity) > 0.0 else float(quantity)
            for quantity in bundle.target_quantity_by_symbol["AAPL"]
        ]
        return ExecutionArrayBundle(
            timestamp_ms=bundle.timestamp_ms,
            target_quantity_by_symbol={"AAPL": target},
        )

    return StrategyDefinition(
        strategy_id="short_like_target_fixture",
        feature_specs=("close", "open"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        risk_rules=(force_short_target,),
        bar_model=bar_model,
    )


def _build_request_for_strategy(
    *,
    engine: BacktestEngine,
    strategy: StrategyDefinition,
    start_ms: int,
    end_ms: int,
    execution: ExecutionConfig | None = None,
) -> BacktestRequest:
    return BacktestRequest(
        symbols=["AAPL"],
        timeframe="1m",
        start_ms=start_ms,
        end_ms=end_ms,
        strategy=StrategyConfig(strategy_id=strategy.strategy_id),
        execution=execution or ExecutionConfig(),
        initial_capital=10_000.0,
        engine=engine,
    )


if __name__ == "__main__":
    unittest.main()
