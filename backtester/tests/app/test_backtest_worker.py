import os
import unittest
from dataclasses import replace

import pandas as pd
from app.backtest_worker import (
    BacktestWorker,
    CompactBacktestResult,
    ProcessBacktestChildExecutor,
    execute_backtest_child,
)
from app.config import BacktesterConfig
from domain.enums import BacktestEngine, BacktestRunStatus
from domain.types import (
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestResult,
    BacktestRunQuery,
    BacktestRunRecord,
    ExecutionConfig,
    PortfolioSnapshot,
    StrategyConfig,
)


class _FakeHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars
        self.calls: list[dict] = []

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        self.calls.append(kwargs)
        return self._bars.copy()


class _FakeRunRepository:
    def __init__(self, batches: list[list[BacktestRunRecord]]) -> None:
        self._batches = list(batches)
        self.queries: list[BacktestRunQuery] = []

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        self.queries.append(query)
        if not self._batches:
            return []
        return self._batches.pop(0)


class _FakeLifecycle:
    def __init__(self, claim_results: list[bool]) -> None:
        self._claim_results = list(claim_results)
        self.claims: list[dict] = []
        self.completions: list[dict] = []

    def conditional_update(self, **kwargs) -> bool:
        self.claims.append(kwargs)
        return self._claim_results.pop(0)

    def complete(self, **kwargs) -> bool:
        self.completions.append(kwargs)
        return True


class _FakeChildExecutor:
    def __init__(self, result: CompactBacktestResult) -> None:
        self._result = result
        self.snapshots: list[BacktestRequestSnapshot] = []

    def execute(self, snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
        self.snapshots.append(snapshot)
        return self._result


class TestBacktestWorker(unittest.TestCase):
    def test_default_poll_interval_is_one_second(self) -> None:
        self.assertEqual(BacktesterConfig().worker_poll_interval_seconds, 1.0)

    def test_selects_fifo_with_run_id_tie_breaker_and_persists_completion(self) -> None:
        newer = _queued_run("run-newer", submitted_at_ms=300)
        tie_later = _queued_run("run-b", submitted_at_ms=100)
        selected = _queued_run("run-a", submitted_at_ms=100)
        repository = _FakeRunRepository([[newer, tie_later, selected]])
        lifecycle = _FakeLifecycle([True])
        compact = _compact_result()
        executor = _FakeChildExecutor(compact)
        worker = BacktestWorker(
            repository=repository,
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 2_000]).__next__,
        )

        processed = worker.run_once()

        self.assertTrue(processed)
        self.assertEqual(repository.queries, [BacktestRunQuery(status=BacktestRunStatus.QUEUED)])
        self.assertEqual(executor.snapshots, [selected.request_snapshot])
        self.assertEqual(
            lifecycle.claims,
            [
                {
                    "run_id": "run-a",
                    "expected_status": BacktestRunStatus.QUEUED,
                    "new_status": BacktestRunStatus.RUNNING,
                    "started_at_ms": 1_000,
                }
            ],
        )
        self.assertEqual(len(lifecycle.completions), 1)
        completion = lifecycle.completions[0]
        self.assertEqual(completion["run_id"], "run-a")
        self.assertEqual(completion["expected_status"], BacktestRunStatus.RUNNING)
        self.assertEqual(completion["completed_at_ms"], 2_000)
        self.assertEqual(completion["execution_duration_ms"], 17)
        self.assertEqual(completion["result"].metrics, compact.metrics)
        self.assertEqual(completion["result"].diagnostics, compact.diagnostics)
        self.assertEqual(completion["result"].fills, compact.fills)
        self.assertEqual(completion["result"].trades, compact.trades)
        self.assertEqual(completion["result"].equity_curve, [])

    def test_failed_claim_reloads_queue_without_executing_stale_request(self) -> None:
        lost = _queued_run("run-lost", submitted_at_ms=100)
        winner = _queued_run("run-winner", submitted_at_ms=200)
        repository = _FakeRunRepository([[lost, winner], [winner]])
        lifecycle = _FakeLifecycle([False, True])
        executor = _FakeChildExecutor(_compact_result())
        worker = BacktestWorker(
            repository=repository,
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 1_100, 2_000]).__next__,
        )

        self.assertTrue(worker.run_once())

        self.assertEqual(len(repository.queries), 2)
        self.assertEqual(
            [claim["run_id"] for claim in lifecycle.claims],
            ["run-lost", "run-winner"],
        )
        self.assertEqual(executor.snapshots, [winner.request_snapshot])

    def test_idle_worker_sleeps_for_configured_interval(self) -> None:
        sleeps: list[float] = []
        worker = BacktestWorker(
            repository=_FakeRunRepository([[]]),
            lifecycle=_FakeLifecycle([]),
            child_executor=_FakeChildExecutor(_compact_result()),
            poll_interval_seconds=2.5,
            sleep=sleeps.append,
        )

        worker.run_forever(stop_requested=lambda: bool(sleeps))

        self.assertEqual(sleeps, [2.5])


class TestBacktestChildExecution(unittest.TestCase):
    def test_process_executor_runs_request_in_spawned_child(self) -> None:
        snapshot = BacktestRequestSnapshot.from_request(_request())
        executor = ProcessBacktestChildExecutor(execute_fn=_return_process_identity)

        compact = executor.execute(snapshot)

        self.assertNotEqual(compact.diagnostics["process_id"], os.getpid())
        self.assertEqual(compact.request, snapshot.to_request())

    def test_vectorized_and_event_driven_children_run_full_market_data_path(self) -> None:
        for engine in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
            with self.subTest(engine=engine):
                request = replace(_request(), engine=engine, persist_result=True)
                adapter = _FakeHistoricalAdapter(_bars())

                compact = execute_backtest_child(
                    BacktestRequestSnapshot.from_request(request),
                    data_adapter=adapter,
                )

                self.assertEqual(compact.request.engine, engine)
                self.assertFalse(compact.request.persist_result)
                self.assertEqual(compact.diagnostics["engine"], engine.value)
                self.assertGreater(len(compact.fills), 0)
                self.assertGreaterEqual(compact.execution_duration_ms, 0)
                self.assertEqual(len(adapter.calls), 1)
                self.assertFalse(hasattr(compact, "equity_curve"))


def _queued_run(run_id: str, *, submitted_at_ms: int) -> BacktestRunRecord:
    return BacktestRunRecord(
        run_id=run_id,
        status=BacktestRunStatus.QUEUED,
        submitted_at_ms=submitted_at_ms,
        request_snapshot=BacktestRequestSnapshot.from_request(_request()),
    )


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


def _compact_result() -> CompactBacktestResult:
    request = _request()
    result = BacktestResult(
        request=request,
        equity_curve=[
            PortfolioSnapshot(
                timestamp_ms=request.start_ms,
                cash=request.initial_capital,
                equity=request.initial_capital,
            )
        ],
        metrics={"total_return_pct": 1.25},
        diagnostics={"engine": "vectorized"},
    )
    return CompactBacktestResult.from_result(result, execution_duration_ms=17)


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


if __name__ == "__main__":
    unittest.main()
