import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from multiprocessing import active_children
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

import app.backtest_child as child_module
from app.backtest_child import (
    ChildExitUnconfirmedError,
    CompactBacktestFailure,
    CompactBacktestResult,
    ProcessBacktestChildExecutor,
)
from app.backtest_worker import BacktestWorker, ExecutionOperationalError
from app.config import BacktesterConfig
from domain.enums import BacktestRunStatus
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


class _FakeRunRepository:
    def __init__(self, batches: list[list[BacktestRunRecord]]) -> None:
        self._batches = list(batches)
        self.queries: list[BacktestRunQuery] = []

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        self.queries.append(query)
        if not self._batches:
            return []
        return self._batches.pop(0)

    def next_queued(self) -> BacktestRunRecord | None:
        queued = self.list(
            BacktestRunQuery(status=BacktestRunStatus.QUEUED, membership="standalone")
        )
        return min(queued, key=lambda run: (run.submitted_at_ms, run.run_id)) if queued else None


class _StatusFilteringRunRepository:
    def __init__(self, runs: list[BacktestRunRecord]) -> None:
        self._runs = runs
        self.queries: list[BacktestRunQuery] = []

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        self.queries.append(query)
        return [run for run in self._runs if run.status is query.status]

    def next_queued(self) -> BacktestRunRecord | None:
        queued = self.list(
            BacktestRunQuery(status=BacktestRunStatus.QUEUED, membership="standalone")
        )
        return min(queued, key=lambda run: (run.submitted_at_ms, run.run_id)) if queued else None


class _FakeLifecycle:
    def __init__(
        self,
        claim_results: list[bool | Exception],
        completion_results: list[bool | Exception] | None = None,
    ) -> None:
        self._claim_results = list(claim_results)
        self._completion_results = list(completion_results or [])
        self.claims: list[dict] = []
        self.completions: list[dict] = []
        self.faults: list[dict] = []
        self.reconciliations: list[int] = []

    def execution_slot(self) -> dict:
        return {"owner_token": None, "run_id": None, "fault_code": None, "fault_message": None}

    def claim_execution(self, *, run_id: str, owner_token: str, started_at_ms: int) -> bool:
        return self.conditional_update(
            run_id=run_id,
            expected_status=BacktestRunStatus.QUEUED,
            new_status=BacktestRunStatus.RUNNING,
            started_at_ms=started_at_ms,
        )

    def settle_failure(
        self,
        *,
        run_id: str,
        owner_token: str,
        completed_at_ms: int,
        error_code: str,
        error_message: str,
    ) -> bool:
        return self.conditional_update(
            run_id=run_id,
            expected_status=BacktestRunStatus.RUNNING,
            new_status=BacktestRunStatus.FAILED,
            completed_at_ms=completed_at_ms,
            error_code=error_code,
            error_message=error_message,
        )

    def settle_success(
        self,
        *,
        run_id: str,
        owner_token: str,
        completed_at_ms: int,
        result: BacktestResult,
        execution_duration_ms: int,
    ) -> bool:
        return self.complete(
            run_id=run_id,
            expected_status=BacktestRunStatus.RUNNING,
            completed_at_ms=completed_at_ms,
            result=result,
            execution_duration_ms=execution_duration_ms,
        )

    def reconcile_execution(self, *, completed_at_ms: int) -> int:
        self.reconciliations.append(completed_at_ms)
        return 0

    def record_execution_fault(
        self, *, run_id: str, owner_token: str, code: str, message: str
    ) -> bool:
        self.faults.append({"run_id": run_id, "code": code, "message": message})
        return True

    def conditional_update(self, **kwargs) -> bool:
        self.claims.append(kwargs)
        result = self._claim_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def complete(self, **kwargs) -> bool:
        self.completions.append(kwargs)
        result = self._completion_results.pop(0) if self._completion_results else True
        if isinstance(result, Exception):
            raise result
        return result


class _SlotTrackingLifecycle(_FakeLifecycle):
    def __init__(self) -> None:
        super().__init__([True])
        self.owner_token: str | None = None
        self.fault_code: str | None = None
        self.marker: Path | None = None

    def execution_slot(self) -> dict:
        return {
            "owner_token": self.owner_token,
            "run_id": "run-descendant" if self.owner_token else None,
            "fault_code": self.fault_code,
            "fault_message": None,
        }

    def claim_execution(self, *, run_id: str, owner_token: str, started_at_ms: int) -> bool:
        claimed = super().claim_execution(
            run_id=run_id, owner_token=owner_token, started_at_ms=started_at_ms
        )
        if claimed:
            self.owner_token = owner_token
        return claimed

    def settle_success(self, **kwargs) -> bool:
        if self.marker is None:
            raise AssertionError("Descendant identities must be recorded before settlement")
        if any(_process_exists(pid) for pid in _descendant_ids(self.marker)):
            raise AssertionError("Execution processes must be reaped before settlement")
        settled = super().settle_success(**kwargs)
        if settled:
            self.owner_token = None
        return settled

    def record_execution_fault(
        self, *, run_id: str, owner_token: str, code: str, message: str
    ) -> bool:
        recorded = super().record_execution_fault(
            run_id=run_id, owner_token=owner_token, code=code, message=message
        )
        if recorded:
            self.fault_code = code
        return recorded


class _FakeChildExecutor:
    def __init__(self, result: CompactBacktestResult | CompactBacktestFailure) -> None:
        self._result = result
        self.snapshots: list[BacktestRequestSnapshot] = []

    def execute(
        self,
        snapshot: BacktestRequestSnapshot,
    ) -> CompactBacktestResult | CompactBacktestFailure:
        self.snapshots.append(snapshot)
        return self._result


class _UnconfirmedExitExecutor:
    def execute(self, snapshot: BacktestRequestSnapshot):
        raise ChildExitUnconfirmedError("Child descendants remain active")


class TestBacktestWorker(unittest.TestCase):
    def test_uses_durable_turn_order_for_batch_and_standalone_requests(self) -> None:
        standalone = _queued_run("standalone", submitted_at_ms=1)
        member = replace(
            _queued_run("member", submitted_at_ms=0), batch_id="batch", member_ordinal=0
        )

        class TurnRepository:
            def __init__(self):
                self.turns = [standalone, member]

            def next_queued(self):
                return self.turns.pop(0) if self.turns else None

        class TurnLifecycle(_FakeLifecycle):
            def __init__(self):
                super().__init__([True, True])
                self.turns = ["standalone", "member"]

            def claim_execution(self, *, run_id, owner_token, started_at_ms):
                if run_id != self.turns.pop(0):
                    return False
                return super().claim_execution(
                    run_id=run_id, owner_token=owner_token, started_at_ms=started_at_ms
                )

        lifecycle = TurnLifecycle()
        executor = _FakeChildExecutor(_compact_result())
        worker = BacktestWorker(
            repository=TurnRepository(),
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=lambda: 42,
        )
        self.assertTrue(worker.run_once())
        self.assertTrue(worker.run_once())
        self.assertFalse(worker.run_once())
        self.assertEqual([claim["run_id"] for claim in lifecycle.claims], ["standalone", "member"])
        self.assertEqual(executor.snapshots, [standalone.request_snapshot, member.request_snapshot])

    def test_heartbeat_continues_during_idle_polling_and_long_child(self) -> None:
        idle_heartbeats: list[dict] = []
        idle = BacktestWorker(
            repository=_FakeRunRepository([[]]),
            lifecycle=_FakeLifecycle([]),
            heartbeat_publisher=lambda **fields: idle_heartbeats.append(fields),
            heartbeat_interval_seconds=0.01,
            sleep=lambda _: time.sleep(0.005),
        )
        idle_thread = Thread(
            target=lambda: idle.run_forever(stop_requested=lambda: len(idle_heartbeats) >= 3)
        )
        idle_thread.start()
        idle_thread.join(timeout=2)
        self.assertFalse(idle_thread.is_alive())
        self.assertGreaterEqual(len(idle_heartbeats), 3)
        self.assertTrue(all(beat["owner_token"] is None for beat in idle_heartbeats))

        child_started = Event()
        child_release = Event()
        finished = Event()
        active_heartbeats: list[dict] = []

        class LongChild:
            def execute(self, snapshot):
                child_started.set()
                if not child_release.wait(2):
                    raise AssertionError("child was not released")
                return _compact_result()

        active = BacktestWorker(
            repository=_FakeRunRepository([[_queued_run("long", submitted_at_ms=1)], []]),
            lifecycle=_FakeLifecycle([True]),
            child_executor=LongChild(),
            heartbeat_publisher=lambda **fields: active_heartbeats.append(fields),
            heartbeat_interval_seconds=0.01,
            sleep=lambda _: time.sleep(0.005),
        )
        active_thread = Thread(target=lambda: active.run_forever(stop_requested=finished.is_set))
        active_thread.start()
        self.assertTrue(child_started.wait(2))
        deadline = time.monotonic() + 2
        while len([beat for beat in active_heartbeats if beat["owner_token"]]) < 2:
            if time.monotonic() > deadline:
                self.fail("heartbeat stopped while child was executing")
            time.sleep(0.005)
        child_release.set()
        finished.set()
        active_thread.join(timeout=2)
        self.assertFalse(active_thread.is_alive())

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
        self.assertEqual(
            repository.queries,
            [BacktestRunQuery(status=BacktestRunStatus.QUEUED, membership="standalone")],
        )
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

    def test_held_slot_prevents_another_worker_from_executing(self) -> None:
        selected = _queued_run("run-held", submitted_at_ms=100)
        lifecycle = _FakeLifecycle([False])
        lifecycle.execution_slot = lambda: {
            "owner_token": "other-worker",
            "run_id": "other-run",
            "fault_code": None,
            "fault_message": None,
        }
        executor = _FakeChildExecutor(_compact_result())
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=executor,
        )

        self.assertFalse(worker.run_once())
        self.assertEqual(executor.snapshots, [])

    def test_unconfirmed_child_exit_keeps_capacity_occupied(self) -> None:
        selected = _queued_run("run-uncertain", submitted_at_ms=100)
        lifecycle = _FakeLifecycle([True])
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=_UnconfirmedExitExecutor(),
        )

        with self.assertRaises(ExecutionOperationalError) as error:
            worker.run_once()

        self.assertEqual(error.exception.code, "child_exit_unconfirmed")
        self.assertEqual(lifecycle.faults[0]["code"], "child_exit_unconfirmed")
        self.assertEqual(len(lifecycle.claims), 1)
        self.assertEqual(lifecycle.completions, [])

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_descendants_are_reaped_before_settlement_releases_slot(self) -> None:
        for execute_fn in (
            _return_with_descendant,
            _return_with_detached_descendant,
            _return_with_double_forked_descendant,
        ):
            with self.subTest(execute_fn=execute_fn.__name__):
                with tempfile.TemporaryDirectory() as directory:
                    marker = Path(directory) / "descendant.pid"
                    lifecycle = _SlotTrackingLifecycle()
                    lifecycle.marker = marker
                    worker = BacktestWorker(
                        repository=_FakeRunRepository(
                            [[_queued_run("run-descendant", submitted_at_ms=100)]]
                        ),
                        lifecycle=lifecycle,
                        child_executor=ProcessBacktestChildExecutor(execute_fn=execute_fn),
                    )
                    before = {child.pid for child in active_children()}
                    try:
                        with patch.dict(os.environ, {"BACKTEST_DESCENDANT_PID_FILE": str(marker)}):
                            self.assertTrue(worker.run_once())
                        self.assertEqual(len(lifecycle.completions), 1)
                        self.assertIsNone(lifecycle.execution_slot()["owner_token"])
                        self.assertIsNone(lifecycle.execution_slot()["fault_code"])
                        self.assertEqual({child.pid for child in active_children()}, before)
                    finally:
                        _stop_test_descendant(marker)

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_unconfirmed_real_detached_descendant_faults_and_retains_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "descendant.pid"
            lifecycle = _SlotTrackingLifecycle()
            worker = BacktestWorker(
                repository=_FakeRunRepository(
                    [[_queued_run("run-descendant", submitted_at_ms=100)]]
                ),
                lifecycle=lifecycle,
                child_executor=ProcessBacktestChildExecutor(
                    execute_fn=_return_with_detached_descendant
                ),
            )
            try:
                with patch.dict(os.environ, {"BACKTEST_DESCENDANT_PID_FILE": str(marker)}):
                    with patch.object(child_module, "_run_child", _supervise_with_denied_signals):
                        with self.assertRaises(ExecutionOperationalError) as error:
                            worker.run_once()
                self.assertEqual(error.exception.code, "child_exit_unconfirmed")
                child_pid, descendant_pid = _descendant_ids(marker)
                self.assertFalse(_process_exists(child_pid))
                self.assertTrue(_process_exists(descendant_pid))
                self.assertEqual(lifecycle.execution_slot()["fault_code"], "child_exit_unconfirmed")
                self.assertIsNotNone(lifecycle.execution_slot()["owner_token"])
                self.assertEqual(lifecycle.completions, [])
                self.assertEqual(len(lifecycle.claims), 1)
            finally:
                _stop_test_descendant(marker)

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_supervisor_loss_with_detached_descendant_retains_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "descendant.pid"
            lifecycle = _SlotTrackingLifecycle()
            worker = BacktestWorker(
                repository=_FakeRunRepository(
                    [[_queued_run("run-descendant", submitted_at_ms=100)]]
                ),
                lifecycle=lifecycle,
                child_executor=ProcessBacktestChildExecutor(
                    execute_fn=_kill_supervisor_with_descendant
                ),
            )
            try:
                with patch.dict(os.environ, {"BACKTEST_DESCENDANT_PID_FILE": str(marker)}):
                    with self.assertRaises(ExecutionOperationalError) as error:
                        worker.run_once()
                self.assertEqual(error.exception.code, "child_exit_unconfirmed")
                self.assertTrue(_process_exists(_descendant_ids(marker)[1]))
                self.assertIsNotNone(lifecycle.execution_slot()["owner_token"])
                self.assertEqual(lifecycle.completions, [])
                self.assertEqual(len(lifecycle.claims), 1)
            finally:
                _stop_test_descendant(marker)

    def test_unavailable_containment_faults_without_starting_execution(self) -> None:
        lifecycle = _SlotTrackingLifecycle()
        worker = BacktestWorker(
            repository=_FakeRunRepository([[_queued_run("run-descendant", submitted_at_ms=100)]]),
            lifecycle=lifecycle,
            child_executor=ProcessBacktestChildExecutor(execute_fn=_return_process_identity),
        )
        with patch.object(child_module.sys, "platform", "unsupported"):
            with self.assertRaises(ExecutionOperationalError) as error:
                worker.run_once()
        self.assertEqual(error.exception.code, "child_exit_unconfirmed")
        self.assertEqual(lifecycle.execution_slot()["fault_code"], "child_exit_unconfirmed")
        self.assertIsNotNone(lifecycle.execution_slot()["owner_token"])
        self.assertEqual(lifecycle.completions, [])

    def test_child_reported_failure_persists_sanitized_terminal_state(self) -> None:
        selected = _queued_run("run-failed", submitted_at_ms=100)
        repository = _FakeRunRepository([[selected]])
        lifecycle = _FakeLifecycle([True, True])
        executor = _FakeChildExecutor(
            CompactBacktestFailure(
                error_code="RuntimeError: database password exposed",
                error_message=(
                    "Traceback (most recent call last):\nRuntimeError: database password exposed"
                ),
            )
        )
        worker = BacktestWorker(
            repository=repository,
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 2_000]).__next__,
        )

        self.assertTrue(worker.run_once())

        self.assertEqual(executor.snapshots, [selected.request_snapshot])
        self.assertEqual(len(lifecycle.claims), 2)
        self.assertEqual(
            lifecycle.claims[1],
            {
                "run_id": "run-failed",
                "expected_status": BacktestRunStatus.RUNNING,
                "new_status": BacktestRunStatus.FAILED,
                "completed_at_ms": 2_000,
                "error_code": "backtest_failed",
                "error_message": "Backtest execution failed",
            },
        )
        self.assertEqual(lifecycle.completions, [])

    def test_child_reported_failure_message_is_bounded(self) -> None:
        selected = _queued_run("run-bounded-failure", submitted_at_ms=100)
        lifecycle = _FakeLifecycle([True, True])
        safe_message = "Historical market data is temporarily unavailable. " * 20
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=_FakeChildExecutor(
                CompactBacktestFailure(
                    error_code="market_data_unavailable",
                    error_message=safe_message,
                )
            ),
            now_ms=iter([1_000, 2_000]).__next__,
        )

        self.assertTrue(worker.run_once())

        failure_update = lifecycle.claims[1]
        self.assertEqual(failure_update["error_code"], "market_data_unavailable")
        self.assertEqual(
            failure_update["error_message"],
            safe_message.strip()[:500],
        )
        self.assertEqual(len(failure_update["error_message"]), 500)

    def test_child_reported_failure_code_is_bounded_to_storage_contract(self) -> None:
        selected = _queued_run("run-bounded-code", submitted_at_ms=100)
        lifecycle = _FakeLifecycle([True, True])
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=_FakeChildExecutor(
                CompactBacktestFailure(
                    error_code="a" * 65,
                    error_message="Historical market data is unavailable",
                )
            ),
            now_ms=iter([1_000, 2_000]).__next__,
        )

        self.assertTrue(worker.run_once())

        failure_update = lifecycle.claims[1]
        self.assertEqual(failure_update["error_code"], "backtest_failed")
        self.assertEqual(
            failure_update["error_message"],
            "Historical market data is unavailable",
        )

    @unittest.skipUnless(sys.platform == "linux", "requires Linux subreaping")
    def test_abnormal_child_exit_persists_stable_worker_failure(self) -> None:
        selected = _queued_run("run-crashed", submitted_at_ms=100)
        lifecycle = _FakeLifecycle([True, True])
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=ProcessBacktestChildExecutor(execute_fn=_exit_abnormally),
            now_ms=iter([1_000, 2_000]).__next__,
        )

        with self.assertLogs("app.backtest_worker", level="ERROR") as captured:
            self.assertTrue(worker.run_once())

        self.assertEqual(
            lifecycle.claims[1],
            {
                "run_id": "run-crashed",
                "expected_status": BacktestRunStatus.RUNNING,
                "new_status": BacktestRunStatus.FAILED,
                "completed_at_ms": 2_000,
                "error_code": "child_process_failed",
                "error_message": "Backtest child process failed",
            },
        )
        self.assertEqual(lifecycle.completions, [])
        self.assertIn(
            "Child reported execution failure".lower(), "\n".join(captured.output).lower()
        )

    def test_startup_reconciles_running_runs_before_claiming_queued_work(self) -> None:
        running_a = replace(
            _queued_run("run-running-a", submitted_at_ms=100),
            status=BacktestRunStatus.RUNNING,
            started_at_ms=500,
        )
        running_b = replace(
            _queued_run("run-running-b", submitted_at_ms=200),
            status=BacktestRunStatus.RUNNING,
            started_at_ms=600,
        )
        queued = _queued_run("run-queued", submitted_at_ms=300)
        succeeded = replace(
            _queued_run("run-succeeded", submitted_at_ms=400),
            status=BacktestRunStatus.SUCCEEDED,
            started_at_ms=700,
            completed_at_ms=800,
        )
        failed = replace(
            _queued_run("run-failed", submitted_at_ms=500),
            status=BacktestRunStatus.FAILED,
            started_at_ms=700,
            completed_at_ms=800,
        )
        repository = _StatusFilteringRunRepository(
            [queued, running_a, succeeded, running_b, failed]
        )
        lifecycle = _FakeLifecycle([True, True, True])
        executor = _FakeChildExecutor(_compact_result())
        worker = BacktestWorker(
            repository=repository,
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 1_001, 1_002, 1_003]).__next__,
        )

        worker.run_forever(stop_requested=lambda: bool(executor.snapshots))

        self.assertEqual(lifecycle.reconciliations, [1_000])
        self.assertEqual(
            repository.queries,
            [BacktestRunQuery(status=BacktestRunStatus.QUEUED, membership="standalone")],
        )
        self.assertEqual(
            lifecycle.claims,
            [
                {
                    "run_id": "run-queued",
                    "expected_status": BacktestRunStatus.QUEUED,
                    "new_status": BacktestRunStatus.RUNNING,
                    "started_at_ms": 1_001,
                }
            ],
        )
        self.assertEqual(executor.snapshots, [queued.request_snapshot])
        self.assertEqual(len(lifecycle.completions), 1)

    def test_failure_persistence_error_terminates_without_retrying_or_next_run(self) -> None:
        selected = _queued_run("run-failed", submitted_at_ms=100)
        later = _queued_run("run-later", submitted_at_ms=200)
        lifecycle = _FakeLifecycle([True, RuntimeError("failure persistence unavailable")])
        executor = _FakeChildExecutor(
            CompactBacktestFailure(
                error_code="market_data_unavailable",
                error_message="Historical market data is unavailable",
            )
        )
        worker = BacktestWorker(
            repository=_FakeRunRepository([[later, selected]]),
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 2_000]).__next__,
        )

        with self.assertLogs("app.backtest_worker", level="ERROR") as captured:
            with self.assertRaisesRegex(
                RuntimeError,
                "failure persistence unavailable",
            ):
                worker.run_once()

        self.assertEqual(executor.snapshots, [selected.request_snapshot])
        self.assertEqual(len(lifecycle.claims), 2)
        self.assertEqual(lifecycle.completions, [])
        self.assertIn(
            "failure persistence unavailable",
            "\n".join(captured.output),
        )

    def test_completion_persistence_error_terminates_without_retrying(self) -> None:
        selected = _queued_run("run-completion-failed", submitted_at_ms=100)
        lifecycle = _FakeLifecycle(
            [True],
            completion_results=[RuntimeError("completion persistence unavailable")],
        )
        executor = _FakeChildExecutor(_compact_result())
        worker = BacktestWorker(
            repository=_FakeRunRepository([[selected]]),
            lifecycle=lifecycle,
            child_executor=executor,
            now_ms=iter([1_000, 2_000]).__next__,
        )

        with self.assertLogs("app.backtest_worker", level="ERROR") as captured:
            with self.assertRaisesRegex(
                RuntimeError,
                "completion persistence unavailable",
            ):
                worker.run_once()

        self.assertEqual(executor.snapshots, [selected.request_snapshot])
        self.assertEqual(len(lifecycle.completions), 1)
        self.assertIn(
            "completion persistence unavailable",
            "\n".join(captured.output),
        )

    def test_terminal_persistence_fault_is_published_before_worker_exit(self) -> None:
        heartbeats: list[dict] = []
        worker = BacktestWorker(
            repository=_FakeRunRepository([[_queued_run("run-fault", submitted_at_ms=100)]]),
            lifecycle=_FakeLifecycle(
                [True], completion_results=[RuntimeError("storage unavailable")]
            ),
            child_executor=_FakeChildExecutor(_compact_result()),
            heartbeat_publisher=lambda **fields: heartbeats.append(fields),
            heartbeat_interval_seconds=0.01,
        )
        with self.assertLogs("app.backtest_worker", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
                worker.run_forever()
        self.assertEqual(heartbeats[-1]["fault_code"], "terminal_persistence_failed")
        self.assertIsNotNone(heartbeats[-1]["owner_token"])

    def test_failed_run_is_not_automatically_executed_again(self) -> None:
        selected = _queued_run("run-no-retry", submitted_at_ms=100)
        repository = _FakeRunRepository([[selected], []])
        lifecycle = _FakeLifecycle([True, True])
        executor = _FakeChildExecutor(
            CompactBacktestFailure(
                error_code="backtest_failed",
                error_message="Backtest execution failed",
            )
        )
        sleeps: list[float] = []
        worker = BacktestWorker(
            repository=repository,
            lifecycle=lifecycle,
            child_executor=executor,
            sleep=sleeps.append,
        )

        worker.run_forever(stop_requested=lambda: bool(sleeps))

        self.assertEqual(executor.snapshots, [selected.request_snapshot])
        self.assertEqual(len(lifecycle.claims), 2)
        self.assertEqual(lifecycle.completions, [])
        self.assertEqual(sleeps, [1.0])

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
            strategy_version=1,
        ),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
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


def _return_with_descendant(snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
    descendant = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(os.environ["BACKTEST_DESCENDANT_PID_FILE"]).write_text(f"{os.getpid()} {descendant.pid}")
    return _return_process_identity(snapshot)


def _return_with_detached_descendant(snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
    descendant = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(os.environ["BACKTEST_DESCENDANT_PID_FILE"]).write_text(f"{os.getpid()} {descendant.pid}")
    return _return_process_identity(snapshot)


def _return_with_double_forked_descendant(
    snapshot: BacktestRequestSnapshot,
) -> CompactBacktestResult:
    marker = Path(os.environ["BACKTEST_DESCENDANT_PID_FILE"])
    script = (
        "import os, pathlib, signal, time; "
        "parent = os.getpid(); child = os.fork(); "
        "os._exit(0) if child else None; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(marker)!r}).write_text(f'{os.getpid()} {{parent}} {{os.getpid()}}'); "
        "time.sleep(30)"
    )
    subprocess.Popen(
        [sys.executable, "-c", script],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    return _return_process_identity(snapshot)


def _supervise_with_denied_signals(connection, execute_fn, snapshot) -> None:
    with patch.object(child_module.os, "kill", side_effect=PermissionError("signal denied")):
        child_module._run_child(connection, execute_fn, snapshot)


def _kill_supervisor_with_descendant(snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
    _return_with_detached_descendant(snapshot)
    os.kill(os.getppid(), signal.SIGKILL)
    os._exit(17)


def _descendant_ids(marker: Path) -> tuple[int, ...]:
    return tuple(int(pid) for pid in marker.read_text().split())


def _process_exists(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    return True


def _stop_test_descendant(marker: Path) -> None:
    if not marker.exists():
        return
    for pid in _descendant_ids(marker):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _exit_abnormally(snapshot: BacktestRequestSnapshot) -> CompactBacktestResult:
    os._exit(17)


if __name__ == "__main__":
    unittest.main()
