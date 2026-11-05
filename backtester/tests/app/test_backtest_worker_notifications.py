import unittest
from dataclasses import replace
from threading import Event
from unittest.mock import Mock

from adapters.backtest_events import BacktestControlInbox
from app.backtest_child import CompactBacktestCancelled, ProcessBacktestChildExecutor
from app.backtest_worker import BacktestWorker, ExecutionOperationalError
from domain.enums import BacktestRunStatus
from tests.app.test_backtest_worker import _FakeLifecycle, _FakeRunRepository, _queued_run


class NotificationWorkerTests(unittest.TestCase):
    def inbox(self):
        inbox = Mock(spec=BacktestControlInbox)
        inbox.ready = Event()

        def take():
            inbox.ready.clear()
            return {"1-0"}

        inbox.take.side_effect = take
        return inbox

    def test_child_wait_does_not_query_storage_without_notification_and_ack_follows_settlement(
        self,
    ):
        run = _queued_run("run-1", submitted_at_ms=100)
        repository = _FakeRunRepository([[run]])
        get_run = Mock(wraps=repository.get)
        repository.get = get_run
        inbox = self.inbox()
        lifecycle = _FakeLifecycle([True])
        testcase = self

        class Child(ProcessBacktestChildExecutor):
            def execute(self, snapshot, *, on_poll=None):
                assert on_poll is not None
                testcase.assertFalse(on_poll())
                for _ in range(100):
                    testcase.assertFalse(on_poll())
                testcase.assertEqual(get_run.call_count, 1)
                repository.selected = replace(run, status=BacktestRunStatus.CANCELLING)
                inbox.ready.set()
                testcase.assertTrue(on_poll())
                inbox.acknowledge.assert_not_called()
                return CompactBacktestCancelled()

        worker = BacktestWorker(
            repository=repository, lifecycle=lifecycle, child_executor=Child(), inbox=inbox
        )
        worker.run_forever(stop_requested=lambda: bool(lifecycle.cancellations))
        self.assertEqual(len(lifecycle.cancellations), 1)
        inbox.acknowledge.assert_called_once_with({"1-0"})
        self.assertEqual(lifecycle.completions, [])

    def test_idle_worker_waits_without_repeated_database_reads(self):
        repository = _FakeRunRepository([[]])
        inbox = self.inbox()
        waits = []
        inbox.ready = Mock()
        inbox.ready.wait.side_effect = lambda timeout: waits.append(timeout) or False
        worker = BacktestWorker(repository=repository, lifecycle=_FakeLifecycle([]), inbox=inbox)
        worker.run_forever(stop_requested=lambda: len(waits) == 3)
        self.assertEqual(len(repository.queries), 1)

    def test_held_slot_never_acknowledges_replayed_commands(self):
        lifecycle = _FakeLifecycle([])
        lifecycle.execution_slot = Mock(
            return_value={"owner_token": "old", "run_id": "run-1", "fault_code": None}
        )
        inbox = self.inbox()
        worker = BacktestWorker(repository=_FakeRunRepository([]), lifecycle=lifecycle, inbox=inbox)
        with self.assertRaises(ExecutionOperationalError), self.assertLogs("app.backtest_worker"):
            worker.run_forever()
        inbox.acknowledge.assert_not_called()

    def test_transient_state_read_failure_retries_notification_without_failing_run(self):
        repository = _FakeRunRepository([])
        repository.get = Mock(side_effect=ConnectionError("offline"))
        inbox = self.inbox()
        inbox.ready.set()
        worker = BacktestWorker(repository=repository, lifecycle=_FakeLifecycle([]), inbox=inbox)
        with self.assertLogs("app.backtest_worker"):
            self.assertFalse(worker._control_cancellation("run-1"))
        self.assertTrue(inbox.ready.is_set())
        inbox.acknowledge.assert_not_called()
