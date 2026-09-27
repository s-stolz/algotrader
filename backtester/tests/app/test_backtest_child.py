"""Backtest child execution and process-supervisor tests."""

import os
import sys
import time
import unittest
from dataclasses import replace
from multiprocessing import active_children
from threading import Event
from unittest.mock import MagicMock, patch

import pandas as pd
from app.backtest_child import (
    ChildExitUnconfirmedError,
    CompactBacktestCancelled,
    CompactBacktestFailure,
    CompactBacktestResult,
    ProcessBacktestChildExecutor,
    _supervise_execution,
    execute_backtest_child,
)
from domain.enums import BacktestEngine
from domain.types import (
    BacktestRequest,
    BacktestRequestSnapshot,
    ExecutionConfig,
    StrategyConfig,
)


class _FakeHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars
        self.calls: list[dict] = []

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        self.calls.append(kwargs)
        return self._bars.copy()


class _FailingHistoricalAdapter:
    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        raise RuntimeError("database password exposed")


class TestBacktestChildExecution(unittest.TestCase):
    def test_cancellation_after_result_still_stops_a_child_waiting_to_exit(self) -> None:
        cancellation = Event()
        parent, child, process = MagicMock(), MagicMock(), MagicMock()
        outcome = CompactBacktestFailure("backtest_failed", "Backtest execution failed")

        def receive():
            cancellation.set()
            return outcome

        parent.poll.return_value = True
        parent.recv.side_effect = receive
        process.is_alive.side_effect = [True, False, False]
        process.exitcode = 0
        context = MagicMock()
        context.Pipe.return_value = (parent, child)
        context.Process.return_value = process
        with patch("app.backtest_child.get_context", return_value=context):
            result = _supervise_execution(
                _return_process_identity,
                BacktestRequestSnapshot.from_request(_request()),
                cancellation,
            )
        self.assertIsInstance(result, CompactBacktestCancelled)
        process.terminate.assert_called_once()
        process.join.assert_called()

    def test_unavailable_exact_version_fails_before_loading_candles(self) -> None:
        for strategy_id, version in (
            ("sma_crossover", None),
            ("sma_crossover", 999),
            ("retired", 1),
        ):
            with self.subTest(strategy_id=strategy_id, version=version):
                request = replace(
                    _request(),
                    strategy=replace(
                        _request().strategy,
                        strategy_id=strategy_id,
                        strategy_version=version,
                    ),
                )
                adapter = _FakeHistoricalAdapter(_bars())

                outcome = execute_backtest_child(
                    BacktestRequestSnapshot.from_request(request),
                    data_adapter=adapter,
                )

                self.assertEqual(
                    outcome,
                    CompactBacktestFailure(
                        error_code="strategy_version_unavailable",
                        error_message="Exact strategy version is unavailable",
                    ),
                )
                self.assertEqual(adapter.calls, [])

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_process_executor_runs_request_in_spawned_child(self) -> None:
        snapshot = BacktestRequestSnapshot.from_request(_request())
        executor = ProcessBacktestChildExecutor(execute_fn=_return_process_identity)

        compact = executor.execute(snapshot)

        if not isinstance(compact, CompactBacktestResult):
            self.fail(f"Expected successful child result, got {compact!r}")
        self.assertNotEqual(compact.diagnostics["process_id"], os.getpid())
        self.assertEqual(compact.request, snapshot.to_request())

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_long_child_can_be_observed_and_is_reaped_before_result(self) -> None:
        snapshot = BacktestRequestSnapshot.from_request(_request())
        executor = ProcessBacktestChildExecutor(execute_fn=_return_after_pause)
        polls: list[float] = []

        compact = executor.execute(snapshot, on_poll=lambda: polls.append(time.monotonic()))

        if not isinstance(compact, CompactBacktestResult):
            self.fail(f"Expected successful child result, got {compact!r}")
        self.assertGreaterEqual(len(polls), 1)
        self.assertNotEqual(compact.diagnostics["process_id"], os.getpid())

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_observation_error_stops_and_reaps_child(self) -> None:
        snapshot = BacktestRequestSnapshot.from_request(_request())
        executor = ProcessBacktestChildExecutor(execute_fn=_return_after_pause)
        before = {child.pid for child in active_children()}

        with self.assertRaisesRegex(ChildExitUnconfirmedError, "supervisor interrupted"):
            executor.execute(snapshot, on_poll=lambda: _fail_observation())

        self.assertEqual({child.pid for child in active_children()}, before)

    def test_vectorized_and_event_driven_children_run_full_market_data_path(self) -> None:
        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine):
                request = replace(_request(), engine=engine, persist_result=True)
                adapter = _FakeHistoricalAdapter(_bars())

                compact = execute_backtest_child(
                    BacktestRequestSnapshot.from_request(request),
                    data_adapter=adapter,
                )

                if not isinstance(compact, CompactBacktestResult):
                    self.fail(f"Expected successful child result, got {compact!r}")
                self.assertEqual(compact.request.engine, engine)
                self.assertFalse(compact.request.persist_result)
                self.assertEqual(compact.diagnostics["engine"], engine.value)
                self.assertGreater(len(compact.fills), 0)
                self.assertGreaterEqual(compact.execution_duration_ms, 0)
                self.assertEqual(len(adapter.calls), 1)
                self.assertFalse(hasattr(compact, "equity_curve"))
                self.assertIsNotNone(compact.replay_descriptor)
                self.assertEqual(compact.to_result().replay_descriptor, compact.replay_descriptor)

    def test_execution_exception_returns_generic_failure_and_logs_details(self) -> None:
        snapshot = BacktestRequestSnapshot.from_request(_request())

        with self.assertLogs("app.backtest_worker", level="ERROR") as captured:
            outcome = execute_backtest_child(
                snapshot,
                data_adapter=_FailingHistoricalAdapter(),
            )

        if not isinstance(outcome, CompactBacktestFailure):
            self.fail(f"Expected child failure, got {outcome!r}")
        self.assertEqual(
            outcome,
            CompactBacktestFailure(
                error_code="backtest_failed",
                error_message="Backtest execution failed",
            ),
        )
        self.assertIn("RuntimeError: database password exposed", "\n".join(captured.output))
        self.assertNotIn("password", outcome.error_message)


def _request() -> BacktestRequest:
    start_ms = 1_700_000_000_000
    return BacktestRequest(
        symbols=["AAPL"],
        exchange="NASDAQ",
        timeframe="M1",
        start_ms=start_ms,
        end_ms=start_ms + (9 * 60_000),
        strategy=StrategyConfig(
            strategy_id="sma_crossover",
            parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0},
            strategy_version=1,
        ),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
    )


def _bars() -> pd.DataFrame:
    start_ms = 1_700_000_000_000
    minute = 60_000
    timestamps = [start_ms - (3 * minute) + (minute * index) for index in range(12)]
    closes = [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
    return pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "symbol": ["AAPL"] * len(timestamps),
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": [1_000.0] * len(timestamps),
        }
    )


def _return_process_identity(
    snapshot: BacktestRequestSnapshot,
) -> CompactBacktestResult:
    return CompactBacktestResult(
        request=snapshot.to_request(),
        fills=[],
        trades=[],
        metrics={},
        diagnostics={"process_id": os.getpid()},
        execution_duration_ms=0,
    )


def _return_after_pause(snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
    time.sleep(0.6)
    return _return_process_identity(snapshot)


def _fail_observation() -> None:
    raise RuntimeError("observation failed")


if __name__ == "__main__":
    unittest.main()
