"""Long-lived singleton worker for durable asynchronous backtest runs."""

from __future__ import annotations

import logging
import math
import re
from time import sleep as default_sleep
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from domain.enums import BacktestRunStatus
from domain.types import (
    BacktestRequestSnapshot,
    BacktestResult,
    BacktestRunQuery,
    BacktestRunRecord,
)

from app.backtest_child import (
    _DEFAULT_FAILURE_CODE,
    _DEFAULT_FAILURE_MESSAGE,
    ChildExitUnconfirmedError,
    CompactBacktestFailure,
    CompactBacktestResult,
    ProcessBacktestChildExecutor,
)

_LOGGER = logging.getLogger(__name__)
_PUBLIC_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
_EXCEPTION_DETAIL_PATTERN = re.compile(r"(?:^|\s)[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):")
_MAX_ERROR_MESSAGE_LENGTH = 500


class QueuedRunRepository(Protocol):
    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]: ...


class RunLifecyclePersistence(Protocol):
    def execution_slot(self) -> Mapping[str, Any]: ...

    def claim_execution(self, *, run_id: str, owner_token: str, started_at_ms: int) -> bool: ...

    def settle_failure(
        self,
        *,
        run_id: str,
        owner_token: str,
        completed_at_ms: int,
        error_code: str,
        error_message: str,
    ) -> bool: ...

    def settle_success(
        self,
        *,
        run_id: str,
        owner_token: str,
        completed_at_ms: int,
        result: BacktestResult,
        execution_duration_ms: int,
    ) -> bool: ...

    def reconcile_execution(self, *, completed_at_ms: int) -> int | None: ...

    def record_execution_fault(
        self, *, run_id: str, owner_token: str, code: str, message: str
    ) -> bool: ...

    def conditional_update(
        self,
        *,
        run_id: str,
        expected_status: BacktestRunStatus,
        new_status: BacktestRunStatus,
        started_at_ms: int | None = None,
        completed_at_ms: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> bool: ...

    def complete(
        self,
        *,
        run_id: str,
        expected_status: BacktestRunStatus,
        completed_at_ms: int,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> bool: ...


class BacktestChildExecutor(Protocol):
    def execute(
        self,
        snapshot: BacktestRequestSnapshot,
    ) -> CompactBacktestResult | CompactBacktestFailure: ...


class ExecutionOperationalError(RuntimeError):
    def __init__(self, code: str, run_id: str | None, message: str) -> None:
        self.code = code
        self.run_id = run_id
        super().__init__(message)


class BacktestWorker:
    """Selects, claims, executes, and completes one durable run at a time."""

    def __init__(
        self,
        *,
        repository: QueuedRunRepository,
        lifecycle: RunLifecyclePersistence,
        child_executor: BacktestChildExecutor | None = None,
        poll_interval_seconds: float = 1.0,
        now_ms: Callable[[], int] | None = None,
        sleep: Callable[[float], None] = default_sleep,
    ) -> None:
        if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive and finite")
        self._repository = repository
        self._lifecycle = lifecycle
        self._child_executor = child_executor or ProcessBacktestChildExecutor()
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._now_ms = now_ms or _utc_now_ms
        self._sleep = sleep

    def run_once(self) -> bool:
        """Process one successfully claimed run, or report that the queue is idle."""

        while True:
            queued_runs = self._repository.list(
                BacktestRunQuery(status=BacktestRunStatus.QUEUED, membership="standalone")
            )
            if not queued_runs:
                return False

            selected = min(
                queued_runs,
                key=lambda run: (run.submitted_at_ms, run.run_id),
            )
            owner_token = str(uuid4())
            claimed = self._lifecycle.claim_execution(
                run_id=selected.run_id,
                owner_token=owner_token,
                started_at_ms=self._now_ms(),
            )
            if not claimed:
                slot = self._lifecycle.execution_slot()
                if slot["fault_code"] is not None:
                    raise ExecutionOperationalError(
                        str(slot["fault_code"]),
                        slot["run_id"],
                        str(slot["fault_message"] or "Backtest execution slot is faulted"),
                    )
                if slot["owner_token"] is not None:
                    return False
                continue

            return self._execute_claimed(selected, owner_token)

    def _execute_claimed(self, selected: BacktestRunRecord, owner_token: str) -> bool:
        try:
            outcome = self._child_executor.execute(selected.request_snapshot)
        except ChildExitUnconfirmedError as exc:
            self._record_fault(selected.run_id, owner_token, "child_exit_unconfirmed", str(exc))
            raise ExecutionOperationalError(
                "child_exit_unconfirmed", selected.run_id, str(exc)
            ) from exc
        except Exception:
            _LOGGER.exception(
                "Backtest child process failed",
                extra={"run_id": selected.run_id},
            )
            self._persist_failure(
                run_id=selected.run_id,
                owner_token=owner_token,
                failure=CompactBacktestFailure(
                    error_code="child_process_failed",
                    error_message="Backtest child process failed",
                ),
            )
            return True

        if isinstance(outcome, CompactBacktestFailure):
            error_code, _ = _sanitize_failure(outcome)
            _LOGGER.error(
                "Backtest child reported execution failure",
                extra={"run_id": selected.run_id, "error_code": error_code},
            )
            self._persist_failure(run_id=selected.run_id, owner_token=owner_token, failure=outcome)
            return True

        compact_result = outcome
        try:
            completed = self._lifecycle.settle_success(
                run_id=selected.run_id,
                owner_token=owner_token,
                completed_at_ms=self._now_ms(),
                result=compact_result.to_result(),
                execution_duration_ms=compact_result.execution_duration_ms,
            )
        except Exception:
            _LOGGER.exception(
                "Failed to persist backtest run completion",
                extra={"run_id": selected.run_id},
            )
            self._record_fault(
                selected.run_id,
                owner_token,
                "terminal_persistence_failed",
                "Backtest run completion could not be persisted",
            )
            raise
        if not completed:
            _LOGGER.error(
                "Backtest run completion was not persisted",
                extra={"run_id": selected.run_id},
            )
            self._record_fault(
                selected.run_id,
                owner_token,
                "lost_ownership",
                "Backtest run completion was rejected by storage",
            )
            raise ExecutionOperationalError(
                "lost_ownership",
                selected.run_id,
                f"Backtest run completion was not persisted: {selected.run_id}",
            )
        return True

    def _persist_failure(
        self,
        *,
        run_id: str,
        owner_token: str,
        failure: CompactBacktestFailure,
    ) -> None:
        error_code, error_message = _sanitize_failure(failure)
        try:
            failed = self._lifecycle.settle_failure(
                run_id=run_id,
                owner_token=owner_token,
                completed_at_ms=self._now_ms(),
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:
            _LOGGER.exception(
                "Failed to persist backtest run failure",
                extra={"run_id": run_id},
            )
            self._record_fault(
                run_id,
                owner_token,
                "terminal_persistence_failed",
                "Backtest run failure could not be persisted",
            )
            raise
        if not failed:
            _LOGGER.error(
                "Backtest run failure was not persisted",
                extra={"run_id": run_id},
            )
            self._record_fault(
                run_id,
                owner_token,
                "lost_ownership",
                "Backtest run failure was rejected by storage",
            )
            raise ExecutionOperationalError(
                "lost_ownership", run_id, f"Backtest run failure was not persisted: {run_id}"
            )

    def _record_fault(self, run_id: str, owner_token: str, code: str, message: str) -> None:
        try:
            self._lifecycle.record_execution_fault(
                run_id=run_id, owner_token=owner_token, code=code, message=message
            )
        except Exception:
            _LOGGER.exception("Failed to record backtest execution fault", extra={"run_id": run_id})

    def run_forever(
        self,
        *,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.reconcile_running_runs()
        should_stop = stop_requested or (lambda: False)
        while not should_stop():
            if not self.run_once():
                self._sleep(self._poll_interval_seconds)

    def reconcile_running_runs(self) -> None:
        """Reconcile only after storage confirms the execution slot is free."""

        slot = self._lifecycle.execution_slot()
        if slot["owner_token"] is not None or slot["fault_code"] is not None:
            raise ExecutionOperationalError(
                str(slot["fault_code"] or "ownership_held"),
                slot["run_id"],
                "Previous execution may still be active; operator recovery is required",
            )
        try:
            reconciled = self._lifecycle.reconcile_execution(completed_at_ms=self._now_ms())
        except Exception as exc:
            raise ExecutionOperationalError(
                "reconciliation_failed", None, "Interrupted runs could not be reconciled"
            ) from exc
        if reconciled is None:
            raise ExecutionOperationalError(
                "ownership_held", None, "Execution slot became unavailable during reconciliation"
            )
        if reconciled:
            _LOGGER.warning("Reconciled interrupted backtest runs", extra={"count": reconciled})


def _utc_now_ms() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _sanitize_failure(failure: CompactBacktestFailure) -> tuple[str, str]:
    error_code = failure.error_code.strip()
    if not _PUBLIC_ERROR_CODE_PATTERN.fullmatch(error_code):
        error_code = _DEFAULT_FAILURE_CODE

    error_message = failure.error_message.strip()
    if (
        not error_message
        or "\n" in error_message
        or "traceback" in error_message.lower()
        or _EXCEPTION_DETAIL_PATTERN.search(error_message)
    ):
        error_message = _DEFAULT_FAILURE_MESSAGE

    return error_code, error_message[:_MAX_ERROR_MESSAGE_LENGTH]
