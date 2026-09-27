"""Spawned backtest execution and Linux process-tree supervision."""

from __future__ import annotations

import ctypes
import logging
import os
import signal
import sys
from copy import deepcopy
from dataclasses import dataclass, replace
from multiprocessing import get_context
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from time import perf_counter
from time import sleep as default_sleep
from typing import Callable

from adapters.db_accessor import HistoricalBarDataAdapter
from domain.types import BacktestRequest, BacktestRequestSnapshot, BacktestResult, Fill, Trade
from strategies.registry import (
    StrategyVersionUnavailableError,
    current_strategy,
    resolve_strategy_and_parameters,
)

from app.backtest_runner import run_backtest_with_market_data

_LOGGER = logging.getLogger("app.backtest_worker")
_DEFAULT_FAILURE_CODE = "backtest_failed"
_DEFAULT_FAILURE_MESSAGE = "Backtest execution failed"


@dataclass(frozen=True)
class CompactBacktestResult:
    """Pickle-safe child result that deliberately excludes the equity curve."""

    request: BacktestRequest
    fills: list[Fill]
    trades: list[Trade]
    metrics: dict[str, float]
    diagnostics: dict[str, object]
    execution_duration_ms: int
    replay_descriptor: dict[str, object] | None = None

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
            replay_descriptor=(
                deepcopy(dict(result.replay_descriptor))
                if result.replay_descriptor is not None
                else None
            ),
            execution_duration_ms=max(0, int(execution_duration_ms)),
        )

    def to_result(self) -> BacktestResult:
        return BacktestResult(
            request=self.request,
            fills=deepcopy(self.fills),
            trades=deepcopy(self.trades),
            metrics=deepcopy(self.metrics),
            diagnostics=deepcopy(self.diagnostics),
            replay_descriptor=deepcopy(self.replay_descriptor),
        )


@dataclass(frozen=True)
class CompactBacktestFailure:
    """Pickle-safe child failure containing only public error details."""

    error_code: str
    error_message: str


@dataclass(frozen=True)
class CompactBacktestCancelled:
    """The execution tree was stopped and reaped after durable cancellation."""


class ProcessBacktestChildExecutor:
    """Runs one claimed request in a supervised, spawned process tree."""

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
        *,
        on_poll: Callable[[], bool | None] | None = None,
    ) -> CompactBacktestResult | CompactBacktestFailure | CompactBacktestCancelled:
        if sys.platform != "linux":
            raise ChildExitUnconfirmedError("Backtest supervision requires Linux child subreaping")
        context = get_context("spawn")
        cancel_requested = context.Event()
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_run_child, args=(child, self._execute_fn, snapshot, cancel_requested)
        )
        try:
            process.start()
            child.close()
            return self._wait_for_child(process, parent, on_poll, cancel_requested)
        except ChildExitUnconfirmedError:
            raise
        except BaseException as exc:
            if process.is_alive():
                _stop_child(process)
            raise ChildExitUnconfirmedError(
                "Backtest supervisor interrupted before descendant exit was confirmed"
            ) from exc
        finally:
            child.close()
            parent.close()

    def _wait_for_child(
        self,
        process: BaseProcess,
        parent: Connection,
        on_poll: Callable[[], bool | None] | None,
        cancel_requested,
    ) -> CompactBacktestResult | CompactBacktestFailure | CompactBacktestCancelled:
        outcome = None
        while True:
            if parent.poll(0.2):
                try:
                    outcome = parent.recv()
                except EOFError:
                    pass
                break
            if on_poll is not None and on_poll():
                cancel_requested.set()
            if not process.is_alive():
                break
        while process.is_alive():
            process.join(timeout=0.2)
            if on_poll is not None and on_poll():
                cancel_requested.set()
        process.join()
        if isinstance(outcome, ChildExitUnconfirmedError):
            raise outcome
        if process.exitcode != 0 or not isinstance(outcome, _ReapedChildResult):
            raise ChildExitUnconfirmedError("Backtest supervisor exited without verified tree exit")
        return outcome.result


class ChildExitUnconfirmedError(RuntimeError):
    pass


@dataclass(frozen=True)
class _ReapedChildResult:
    result: CompactBacktestResult | CompactBacktestFailure | CompactBacktestCancelled


def _run_child(
    connection: Connection,
    execute_fn: Callable[[BacktestRequestSnapshot], CompactBacktestResult | CompactBacktestFailure],
    snapshot: BacktestRequestSnapshot,
    cancel_requested,
) -> None:
    try:
        os.setsid()
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        libc.prctl.restype = ctypes.c_int
        # This supervisor never executes strategy code. Orphans stay beneath it
        # even when a descendant double-forks or creates a new session.
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise ChildExitUnconfirmedError("Cannot enable backtest child subreaping")
        result = _supervise_execution(execute_fn, snapshot, cancel_requested)
        _reap_descendants()
        connection.send(_ReapedChildResult(result))
    except BaseException:
        _LOGGER.exception("Backtest process tree exit could not be verified")
        connection.send(ChildExitUnconfirmedError("Backtest descendants have not been reaped"))
    finally:
        connection.close()


def _supervise_execution(
    execute_fn: Callable[[BacktestRequestSnapshot], CompactBacktestResult | CompactBacktestFailure],
    snapshot: BacktestRequestSnapshot,
    cancel_requested,
) -> CompactBacktestResult | CompactBacktestFailure | CompactBacktestCancelled:
    context = get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_execute_child, args=(child, execute_fn, snapshot))
    outcome = None
    try:
        process.start()
        child.close()
        while True:
            if cancel_requested.is_set():
                process.terminate()
                process.join(timeout=2.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2.0)
                if process.is_alive():
                    raise ChildExitUnconfirmedError(
                        "Backtest execution child exit could not be confirmed"
                    )
                return CompactBacktestCancelled()
            if parent.poll(0.2):
                try:
                    outcome = parent.recv()
                except EOFError:
                    pass
                break
            if not process.is_alive():
                break
        while process.is_alive():
            process.join(timeout=0.2)
        process.join()
        if process.exitcode == 0 and isinstance(
            outcome, (CompactBacktestResult, CompactBacktestFailure)
        ):
            return outcome
        return CompactBacktestFailure("child_process_failed", "Backtest child process failed")
    finally:
        parent.close()
        child.close()


def _execute_child(
    connection: Connection,
    execute_fn: Callable[[BacktestRequestSnapshot], CompactBacktestResult | CompactBacktestFailure],
    snapshot: BacktestRequestSnapshot,
) -> None:
    try:
        connection.send(execute_fn(snapshot))
    finally:
        connection.close()


def _reap_descendants() -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        deadline = perf_counter() + 2.0
        while perf_counter() < deadline:
            try:
                # __WALL also includes descendants created by clone without SIGCHLD.
                while os.waitpid(-1, os.WNOHANG | 0x40000000)[0]:
                    pass
            except ChildProcessError:
                # Only ECHILD proves the entire adopted tree is gone. An empty
                # /proc snapshot alone can race with reparenting or exit.
                return
            try:
                for task in Path("/proc/self/task").iterdir():
                    for child in (task / "children").read_text().split():
                        try:
                            os.kill(int(child), sig)
                        except ProcessLookupError:
                            pass
            except OSError as exc:
                raise ChildExitUnconfirmedError("Cannot stop adopted backtest descendants") from exc
            default_sleep(0.05)
    raise ChildExitUnconfirmedError("Backtest descendants have not been reaped")


def _stop_child(process: BaseProcess) -> None:
    if process.pid is None:
        raise ChildExitUnconfirmedError("Backtest child process has no identity")
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.terminate()
    except PermissionError as exc:
        raise ChildExitUnconfirmedError("Cannot stop backtest child") from exc
    process.join(timeout=2.0)
    if process.is_alive():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            process.kill()
        except PermissionError as exc:
            raise ChildExitUnconfirmedError("Cannot kill backtest child") from exc
        process.join(timeout=2.0)
    if process.is_alive():
        raise ChildExitUnconfirmedError("Backtest child exit could not be confirmed")


def execute_backtest_child(
    snapshot: BacktestRequestSnapshot,
    *,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> CompactBacktestResult | CompactBacktestFailure:
    """Resolve and execute the immutable request entirely inside the child."""

    try:
        request = replace(snapshot.to_request(), persist_result=False)
        if request.strategy.strategy_version is None:
            raise StrategyVersionUnavailableError("strategy_version_unavailable")
        try:
            current_strategy(request.strategy.strategy_id)
        except ValueError as exc:
            raise StrategyVersionUnavailableError("strategy_version_unavailable") from exc
        strategy, _ = resolve_strategy_and_parameters(request.strategy)
        started_at = perf_counter()
        result = run_backtest_with_market_data(
            request=request,
            strategy=strategy,
            data_adapter=data_adapter,
        )
        execution_duration_ms = max(0, int(round((perf_counter() - started_at) * 1000)))
        return CompactBacktestResult.from_result(
            result,
            execution_duration_ms=execution_duration_ms,
        )
    except StrategyVersionUnavailableError:
        return CompactBacktestFailure(
            error_code="strategy_version_unavailable",
            error_message="Exact strategy version is unavailable",
        )
    except Exception:
        _LOGGER.exception("Backtest child execution failed")
        return CompactBacktestFailure(
            error_code=_DEFAULT_FAILURE_CODE,
            error_message=_DEFAULT_FAILURE_MESSAGE,
        )
