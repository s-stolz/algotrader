import unittest

import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine, DataGranularity
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.base import BarStrategyModel, StrategyDefinition
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


def _build_request_for_strategy(
    *,
    engine: BacktestEngine,
    strategy: StrategyDefinition,
    start_ms: int,
    end_ms: int,
) -> BacktestRequest:
    return BacktestRequest(
        symbols=["AAPL"],
        timeframe="1m",
        start_ms=start_ms,
        end_ms=end_ms,
        strategy=StrategyConfig(strategy_id=strategy.strategy_id),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
        engine=engine,
    )


if __name__ == "__main__":
    unittest.main()
