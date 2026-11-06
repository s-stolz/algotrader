import unittest
from dataclasses import replace

import pandas as pd
from app.backtest_runner import run_backtest_with_market_data
from domain.enums import BacktestEngine
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class _FakeHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars
        self.calls: list[dict] = []

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        self.calls.append(kwargs)
        bars = self._bars.sort_values("timestamp_ms")
        if kwargs["start_ms"] is not None:
            bars = bars.loc[bars["timestamp_ms"] >= kwargs["start_ms"]]
        bars = bars.loc[bars["timestamp_ms"] < kwargs["end_ms"]]
        if kwargs.get("limit") is not None:
            bars = bars.tail(kwargs["limit"])
        return bars.copy()


class TestRealDataBacktestRunner(unittest.TestCase):
    def _build_request(self) -> BacktestRequest:
        start_ms = 1_700_000_000_000
        end_ms = start_ms + (9 * 60_000)
        return BacktestRequest(
            symbols=["AAPL"],
            timeframe="M1",
            start_ms=start_ms,
            end_ms=end_ms,
            strategy=StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            ),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
        )

    def _build_raw_bars(self) -> pd.DataFrame:
        start_ms = 1_700_000_000_000
        minute = 60_000
        timestamps = [start_ms - (3 * minute) + (minute * i) for i in range(12)]

        return pd.DataFrame(
            {
                "timestamp_ms": timestamps,
                "symbol": ["AAPL"] * 12,
                "open": [
                    13.0,
                    12.0,
                    11.0,
                    10.0,
                    9.0,
                    8.0,
                    9.0,
                    10.0,
                    10.0,
                    11.0,
                    12.0,
                    13.0,
                ],
                "high": [
                    13.5,
                    12.5,
                    11.5,
                    10.5,
                    9.5,
                    8.5,
                    9.5,
                    10.5,
                    10.5,
                    11.5,
                    12.5,
                    13.5,
                ],
                "low": [
                    12.5,
                    11.5,
                    10.5,
                    9.5,
                    8.5,
                    7.5,
                    8.5,
                    9.5,
                    9.5,
                    10.5,
                    11.5,
                    12.5,
                ],
                "close": [
                    13.0,
                    12.0,
                    11.0,
                    10.0,
                    9.0,
                    8.0,
                    9.0,
                    10.0,
                    11.0,
                    10.0,
                    9.0,
                    8.0,
                ],
                "volume": [1_000.0] * 12,
            }
        )

    def test_real_data_path_expands_warmup_and_is_deterministic(self) -> None:
        request = self._build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        adapter = _FakeHistoricalAdapter(self._build_raw_bars())

        result_one = run_backtest_with_market_data(
            request=request,
            strategy=strategy,
            data_adapter=adapter,
        )
        result_two = run_backtest_with_market_data(
            request=request,
            strategy=strategy,
            data_adapter=adapter,
        )

        self.assertEqual(len(adapter.calls), 2)
        expected_fetch_start = request.start_ms - (2 * 60_000)
        self.assertEqual(adapter.calls[0]["start_ms"], expected_fetch_start)
        self.assertEqual(adapter.calls[0]["end_ms"], request.end_ms)
        self.assertEqual(adapter.calls[0]["timeframe"], "M1")
        self.assertEqual(adapter.calls[0]["symbol"], "AAPL")

        self.assertEqual(result_one.metrics, result_two.metrics)
        self.assertEqual(
            [(fill.timestamp_ms, fill.side.value, fill.price) for fill in result_one.fills],
            [(fill.timestamp_ms, fill.side.value, fill.price) for fill in result_two.fills],
        )
        self.assertGreater(len(result_one.fills), 0)
        self.assertGreater(len(result_one.equity_curve), 0)

    def test_real_data_path_resolves_strategy_from_request_when_override_absent(self) -> None:
        request = self._build_request()
        adapter = _FakeHistoricalAdapter(self._build_raw_bars())

        result = run_backtest_with_market_data(
            request=request,
            data_adapter=adapter,
        )

        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(result.diagnostics["strategy_id"], "sma_crossover")
        self.assertGreater(len(result.fills), 0)

    def test_event_driven_real_data_path_uses_streaming_engine(self) -> None:
        base_request = self._build_request()
        request = BacktestRequest(
            symbols=base_request.symbols,
            timeframe=base_request.timeframe,
            start_ms=base_request.start_ms,
            end_ms=base_request.end_ms,
            strategy=base_request.strategy,
            execution=base_request.execution,
            initial_capital=base_request.initial_capital,
            engine=BacktestEngine.EVENT_DRIVEN,
        )
        adapter = _FakeHistoricalAdapter(self._build_raw_bars())

        result = run_backtest_with_market_data(
            request=request,
            data_adapter=adapter,
        )

        expected_fetch_start = request.start_ms - (2 * 60_000)
        self.assertEqual(adapter.calls[0]["start_ms"], expected_fetch_start)
        self.assertEqual(result.diagnostics["engine"], "event_driven")
        self.assertEqual(result.diagnostics["strategy_id"], "sma_crossover")
        self.assertGreater(len(result.fills), 0)

    def test_both_engines_recover_warmup_or_delay_when_history_is_exhausted(self) -> None:
        start_ms = 1_762_387_200_000
        minute = 60_000
        request = replace(
            self._build_request(),
            symbols=["EURUSD"],
            exchange="IC Trading",
            start_ms=start_ms,
            end_ms=start_ms + 30 * minute,
            strategy=StrategyConfig(
                "sma_crossover", {"fast_window": 50, "slow_window": 200, "quantity": 1.0}
            ),
        )
        cases = (
            ("older history available", -210, 0, 0),
            ("older history exhausted", -199, 0, 10),
            ("weekend before start", -210, 2 * 86_400_000, 0),
        )
        for name, first_offset, closure_ms, first_executable_offset in cases:
            with self.subTest(case=name):
                # Ten missing minutes leave only 189 candles in the usual lookback.
                offsets = [
                    offset for offset in range(first_offset, 30) if offset not in range(-20, -10)
                ]
                closes = [float(100 + abs(offset % 40 - 20)) for offset in offsets]
                bars = pd.DataFrame(
                    {
                        "timestamp_ms": [
                            start_ms + offset * minute - (closure_ms if offset < 0 else 0)
                            for offset in offsets
                        ],
                        "symbol": "EURUSD",
                        "open": closes,
                        "high": [close + 1 for close in closes],
                        "low": [close - 1 for close in closes],
                        "close": closes,
                        "volume": 1000.0,
                    }
                )
                results = []
                calls = []
                for engine in BacktestEngine:
                    adapter = _FakeHistoricalAdapter(bars)
                    result = run_backtest_with_market_data(
                        request=replace(request, engine=engine), data_adapter=adapter
                    )
                    self.assertEqual(
                        [snapshot.timestamp_ms for snapshot in result.equity_curve],
                        [
                            start_ms + offset * minute
                            for offset in range(first_executable_offset, 30)
                        ],
                    )
                    self.assertEqual(result.request.start_ms, start_ms)
                    self.assertTrue(
                        all(
                            fill.timestamp_ms > start_ms + first_executable_offset * minute
                            for fill in result.fills
                        )
                    )
                    results.append(result)
                    calls.append(adapter.calls)

                self.assertEqual(results[0].fills, results[1].fills)
                self.assertEqual(results[0].equity_curve, results[1].equity_curve)
                self.assertEqual(results[0].replay_descriptor, results[1].replay_descriptor)
                self.assertEqual(calls[0], calls[1])
                self.assertEqual(len(calls[0]), 2)
                self.assertEqual(calls[0][0]["start_ms"], start_ms - 199 * minute)
                self.assertIsNone(calls[0][1]["start_ms"])
                self.assertEqual(calls[0][1]["end_ms"], start_ms - 199 * minute)
                self.assertTrue(all(call["exchange"] == "IC Trading" for call in calls[0]))

    def test_real_data_path_rejects_mismatched_request_strategy_id(self) -> None:
        request = self._build_request()
        request = BacktestRequest(
            symbols=request.symbols,
            timeframe=request.timeframe,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            strategy=StrategyConfig(
                strategy_id="different_strategy",
                parameters=dict(request.strategy.parameters),
            ),
            execution=request.execution,
            initial_capital=request.initial_capital,
        )
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        adapter = _FakeHistoricalAdapter(self._build_raw_bars())

        with self.assertRaises(ValueError):
            run_backtest_with_market_data(
                request=request,
                strategy=strategy,
                data_adapter=adapter,
            )


if __name__ == "__main__":
    unittest.main()
