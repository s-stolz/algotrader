import unittest
from dataclasses import replace
from unittest.mock import patch

import pandas as pd
from app.backtest_runner import run_backtest, run_backtest_with_market_data, save_backtest_result
from domain.types import BacktestRequest, BacktestResult, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class _RecordingPersistenceAdapter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def save_run_summary(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        self.calls.append(
            {
                "result": result,
                "execution_duration_ms": execution_duration_ms,
            }
        )
        return replace(
            result,
            backtest_run_id="run-auto-1",
            persisted_at=1_778_848_205_123,
        )


class _ExplodingPersistenceAdapter:
    def save_run_summary(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        _ = (result, execution_duration_ms)
        raise AssertionError("persistence adapter should not be called")


class _FailingPersistenceAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def save_run_summary(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        _ = (result, execution_duration_ms)
        self.calls += 1
        raise RuntimeError("database accessor unavailable")


class _TimingAwareHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        _ = kwargs
        from app import backtest_runner

        backtest_runner.perf_counter()
        return self._bars.copy()


class _FakeDatabaseAccessorClient:
    instances: list["_FakeDatabaseAccessorClient"] = []

    def __init__(self) -> None:
        self.saved_summaries: list[dict] = []
        self.closed = False
        self.__class__.instances.append(self)

    def __enter__(self) -> "_FakeDatabaseAccessorClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)
        self.closed = True

    def store_backtest_run_summary(self, summary: dict) -> dict:
        self.saved_summaries.append(dict(summary))
        return {
            "run_id": "run-manual-1",
            "persisted_at": "2026-05-15T12:30:05.123000+00:00",
        }


class TestBacktestPersistenceIntegration(unittest.TestCase):
    def test_opt_in_request_persists_successful_run_and_attaches_metadata(self) -> None:
        adapter = _RecordingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
            persistence_adapter=adapter,
        )

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0]["result"].request, request)
        self.assertIsInstance(adapter.calls[0]["execution_duration_ms"], int)
        self.assertGreaterEqual(adapter.calls[0]["execution_duration_ms"], 0)
        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(result.persisted_at, 1_778_848_205_123)

    def test_default_request_does_not_call_persistence(self) -> None:
        request = _build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
            persistence_adapter=_ExplodingPersistenceAdapter(),
        )

        self.assertIsNone(result.backtest_run_id)
        self.assertIsNone(result.persisted_at)
        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(len(result.fills), 2)

    def test_failed_backtest_does_not_call_persistence(self) -> None:
        request = BacktestRequest(
            symbols=["MSFT"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            persist_result=True,
        )
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaisesRegex(ValueError, "No bars found"):
            run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=_ExplodingPersistenceAdapter(),
            )

    def test_execution_duration_excludes_persistence_call_time(self) -> None:
        adapter = _RecordingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch("app.backtest_runner.perf_counter", side_effect=[10.0, 10.5]):
            result = run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=adapter,
            )

        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(adapter.calls[0]["execution_duration_ms"], 500)

    def test_market_data_loading_time_is_excluded_from_persisted_duration(self) -> None:
        persistence_adapter = _RecordingPersistenceAdapter()
        data_adapter = _TimingAwareHistoricalAdapter(_build_raw_bars_with_warmup())
        request = replace(_build_request(persist_result=True), timeframe="M1")
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch("app.backtest_runner.perf_counter", side_effect=[10.0, 100.0, 100.5]):
            result = run_backtest_with_market_data(
                request=request,
                strategy=strategy,
                data_adapter=data_adapter,
                persistence_adapter=persistence_adapter,
            )

        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(persistence_adapter.calls[0]["execution_duration_ms"], 500)

    def test_persistence_error_surfaces_for_opt_in_request(self) -> None:
        adapter = _FailingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaisesRegex(RuntimeError, "database accessor unavailable"):
            run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=adapter,
            )

        self.assertEqual(adapter.calls, 1)

    def test_manual_save_uses_default_database_accessor_client_surface(self) -> None:
        _FakeDatabaseAccessorClient.instances.clear()
        request = _build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        completed_result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
        )

        with patch(
            "adapters.persistence._import_database_accessor_client",
            return_value=_FakeDatabaseAccessorClient,
            create=True,
        ):
            saved_result = save_backtest_result(
                result=completed_result,
                execution_duration_ms=321,
            )

        self.assertEqual(len(_FakeDatabaseAccessorClient.instances), 1)
        client = _FakeDatabaseAccessorClient.instances[0]
        self.assertTrue(client.closed)
        self.assertEqual(client.saved_summaries[0]["execution_duration_ms"], 321)
        self.assertEqual(client.saved_summaries[0]["symbol"], "AAPL")
        self.assertEqual(client.saved_summaries[0]["trade_count"], 1)
        self.assertEqual(saved_result.backtest_run_id, "run-manual-1")
        self.assertEqual(saved_result.persisted_at, 1_778_848_205_123)
        self.assertIsNone(completed_result.backtest_run_id)


def _build_request(*, persist_result: bool = False) -> BacktestRequest:
    return BacktestRequest(
        symbols=["AAPL"],
        timeframe="1m",
        start_ms=1_700_000_000_000,
        end_ms=1_700_000_540_000,
        strategy=StrategyConfig(strategy_id="sma_crossover"),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
        persist_result=persist_result,
    )


def _build_bars() -> pd.DataFrame:
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


def _build_raw_bars_with_warmup() -> pd.DataFrame:
    start_ms = 1_700_000_000_000
    minute = 60_000
    timestamps = [start_ms - (2 * minute) + (minute * i) for i in range(11)]
    opens = [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0]
    closes = [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]

    return pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "symbol": ["AAPL"] * len(timestamps),
            "open": opens,
            "high": [price + 0.5 for price in opens],
            "low": [price - 0.5 for price in opens],
            "close": closes,
            "volume": [1_000.0] * len(timestamps),
        }
    )


if __name__ == "__main__":
    unittest.main()
