"""Long-lived singleton worker for durable asynchronous backtest runs."""

from __future__ import annotations

import logging
import math
import re
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
from multiprocessing import get_context
from time import perf_counter
from time import sleep as default_sleep
from typing import Callable, Protocol

from adapters.db_accessor import HistoricalBarDataAdapter
from domain.enums import BacktestRunStatus
from domain.types import (
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestResult,
    BacktestRunQuery,
    BacktestRunRecord,
    Fill,
    Trade,
)

from app.backtest_runner import run_backtest_with_market_data

_LOGGER = logging.getLogger(__name__)
_PUBLIC_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
_EXCEPTION_DETAIL_PATTERN = re.compile(r"(?:^|\s)[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):")
_DEFAULT_FAILURE_CODE = "backtest_failed"
_DEFAULT_FAILURE_MESSAGE = "Backtest execution failed"
_MAX_ERROR_MESSAGE_LENGTH = 500


@dataclass(frozen=True)
class CompactBacktestResult:
    """Pickle-safe child result that deliberately excludes the equity curve."""

    request: BacktestRequest
    fills: list[Fill]
    trades: list[Trade]
    metrics: dict[str, float]
    diagnostics: dict[str, object]
    execution_duration_ms: int

    @classmethod
    def from_result(
        cls,
        result: BacktestResult,
        *,
        execution_duration_ms: int,
    ) -> "CompactBacktestResult":
        return cls(
            request=result.request,
            fills=deepcopy(result.fills),
            trades=deepcopy(result.trades),
            metrics=deepcopy(result.metrics),
            diagnostics=deepcopy(result.diagnostics),
            execution_duration_ms=max(0, int(execution_duration_ms)),
        )

    def to_result(self) -> BacktestResult:
        return BacktestResult(
            request=self.request,
            fills=deepcopy(self.fills),
            trades=deepcopy(self.trades),
            metrics=deepcopy(self.metrics),
            diagnostics=deepcopy(self.diagnostics),
        )


@dataclass(frozen=True)
class CompactBacktestFailure:
    """Pickle-safe child failure containing only public error details."""

    error_code: str
    error_message: str


class QueuedRunRepository(Protocol):
    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]: ...


class RunLifecyclePersistence(Protocol):
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


class ProcessBacktestChildExecutor:
    """Runs one claimed request in one managed spawned child process."""

    def __init__(
        self,
        *,
        execute_fn: (
            Callable[
                [BacktestRequestSnapshot],
                CompactBacktestResult | CompactBacktestFailure,
            ]
            | None
        ) = None,
    ) -> None:
        self._execute_fn = execute_fn or execute_backtest_child

    def execute(
        self,
        snapshot: BacktestRequestSnapshot,
    ) -> CompactBacktestResult | CompactBacktestFailure:
        context = get_context("spawn")
        with ProcessPoolExecutor(max_workers=1, mp_context=context) as executor:
            return executor.submit(self._execute_fn, snapshot).result()


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
            queued_runs = self._repository.list(BacktestRunQuery(status=BacktestRunStatus.QUEUED))
            if not queued_runs:
                return False

            selected = min(
                queued_runs,
                key=lambda run: (run.submitted_at_ms, run.run_id),
            )
            claimed = self._lifecycle.conditional_update(
                run_id=selected.run_id,
                expected_status=BacktestRunStatus.QUEUED,
                new_status=BacktestRunStatus.RUNNING,
                started_at_ms=self._now_ms(),
            )
            if not claimed:
                continue

            try:
                outcome = self._child_executor.execute(selected.request_snapshot)
            except Exception:
                _LOGGER.exception(
                    "Backtest child process failed",
                    extra={"run_id": selected.run_id},
                )
                self._persist_failure(
                    run_id=selected.run_id,
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
                self._persist_failure(run_id=selected.run_id, failure=outcome)
                return True

            compact_result = outcome
            try:
                completed = self._lifecycle.complete(
                    run_id=selected.run_id,
                    expected_status=BacktestRunStatus.RUNNING,
                    completed_at_ms=self._now_ms(),
                    result=compact_result.to_result(),
                    execution_duration_ms=compact_result.execution_duration_ms,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to persist backtest run completion",
                    extra={"run_id": selected.run_id},
                )
                raise
            if not completed:
                _LOGGER.error(
                    "Backtest run completion was not persisted",
                    extra={"run_id": selected.run_id},
                )
                raise RuntimeError(f"Backtest run completion was not persisted: {selected.run_id}")
            return True

    def _persist_failure(
        self,
        *,
        run_id: str,
        failure: CompactBacktestFailure,
    ) -> None:
        error_code, error_message = _sanitize_failure(failure)
        try:
            failed = self._lifecycle.conditional_update(
                run_id=run_id,
                expected_status=BacktestRunStatus.RUNNING,
                new_status=BacktestRunStatus.FAILED,
                completed_at_ms=self._now_ms(),
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:
            _LOGGER.exception(
                "Failed to persist backtest run failure",
                extra={"run_id": run_id},
            )
            raise
        if not failed:
            _LOGGER.error(
                "Backtest run failure was not persisted",
                extra={"run_id": run_id},
            )
            raise RuntimeError(f"Backtest run failure was not persisted: {run_id}")

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
        """Fail runs left running by a previously interrupted singleton worker."""

        running_runs = self._repository.list(BacktestRunQuery(status=BacktestRunStatus.RUNNING))
        for run in running_runs:
            try:
                reconciled = self._lifecycle.conditional_update(
                    run_id=run.run_id,
                    expected_status=BacktestRunStatus.RUNNING,
                    new_status=BacktestRunStatus.FAILED,
                    completed_at_ms=self._now_ms(),
                    error_code="worker_interrupted",
                    error_message="Backtest worker was interrupted before completion",
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to reconcile interrupted backtest run",
                    extra={"run_id": run.run_id},
                )
                raise
            if not reconciled:
                _LOGGER.error(
                    "Interrupted backtest run was not reconciled",
                    extra={"run_id": run.run_id},
                )
                raise RuntimeError(f"Interrupted backtest run was not reconciled: {run.run_id}")
            _LOGGER.warning(
                "Reconciled interrupted backtest run",
                extra={"run_id": run.run_id},
            )


def execute_backtest_child(
    snapshot: BacktestRequestSnapshot,
    *,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> CompactBacktestResult | CompactBacktestFailure:
    """Resolve and execute the immutable request entirely inside the child."""

    try:
        request = replace(snapshot.to_request(), persist_result=False)
        started_at = perf_counter()
        result = run_backtest_with_market_data(
            request=request,
            data_adapter=data_adapter,
        )
        execution_duration_ms = max(0, int(round((perf_counter() - started_at) * 1000)))
        return CompactBacktestResult.from_result(
            result,
            execution_duration_ms=execution_duration_ms,
        )
    except Exception:
        _LOGGER.exception("Backtest child execution failed")
        return CompactBacktestFailure(
            error_code=_DEFAULT_FAILURE_CODE,
            error_message=_DEFAULT_FAILURE_MESSAGE,
        )


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
