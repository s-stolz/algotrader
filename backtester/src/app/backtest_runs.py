"""Application use cases for durable backtest run submission and retrieval."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable, Protocol
from uuid import uuid4

from db_accessor_client import normalize_timeframe_code
from domain.enums import (
    BacktestEngine,
    BacktestRunStatus,
    DataGranularity,
    FillTiming,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)
from domain.types import BacktestRequest, BacktestRequestSnapshot, BacktestRunRecord
from strategies.registry import resolve_strategy


class BacktestRunRepository(Protocol):
    """Persistence boundary used by durable run application workflows."""

    def create(self, run: BacktestRunRecord) -> BacktestRunRecord: ...

    def get(self, run_id: str) -> BacktestRunRecord | None: ...


class InvalidBacktestRequestError(ValueError):
    """Raised when a deterministic submission rule is violated."""


class BacktestRunNotFoundError(LookupError):
    """Raised when a requested durable run does not exist."""


class BacktestRunPersistenceError(RuntimeError):
    """Raised when the durable persistence boundary cannot complete an operation."""


class BacktestRunService:
    """Coordinates durable run lifecycle operations without executing backtests."""

    def __init__(
        self,
        *,
        repository: BacktestRunRepository,
        new_run_id: Callable[[], str] | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self._repository = repository
        self._new_run_id = new_run_id or _new_run_id
        self._now_ms = now_ms or _utc_now_ms

    def submit(self, request: BacktestRequest) -> BacktestRunRecord:
        _validate_submission(request)
        run = BacktestRunRecord(
            run_id=self._new_run_id(),
            status=BacktestRunStatus.QUEUED,
            submitted_at_ms=self._now_ms(),
            request_snapshot=BacktestRequestSnapshot.from_request(request),
        )
        try:
            return self._repository.create(run)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc

    def get(self, run_id: str) -> BacktestRunRecord:
        try:
            run = self._repository.get(run_id)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        if run is None:
            raise BacktestRunNotFoundError(f"Backtest run not found: {run_id}")
        return run


def _validate_submission(request: BacktestRequest) -> None:
    _validate_request_shape(request)
    _validate_execution(request)
    _validate_strategy(request)


def _validate_request_shape(request: BacktestRequest) -> None:
    if request.start_ms >= request.end_ms:
        raise InvalidBacktestRequestError("start_ms must be less than end_ms")
    if len(request.symbols) != 1:
        raise InvalidBacktestRequestError("Backtest requests require exactly one symbol")
    if not str(request.symbols[0]).strip():
        raise InvalidBacktestRequestError("Backtest request symbol must be non-empty")
    try:
        normalize_timeframe_code(request.timeframe)
    except ValueError as exc:
        raise InvalidBacktestRequestError(str(exc)) from exc
    if not math.isfinite(request.initial_capital) or request.initial_capital <= 0.0:
        raise InvalidBacktestRequestError("initial_capital must be positive and finite")
    if request.data_granularity != DataGranularity.BAR:
        raise InvalidBacktestRequestError("Backtest requests support bar data only")
    if request.engine not in (BacktestEngine.VECTORIZED, BacktestEngine.EVENT_DRIVEN):
        raise InvalidBacktestRequestError("Unsupported backtest engine")


def _validate_execution(request: BacktestRequest) -> None:
    execution = request.execution
    supported_execution = (
        execution.signal_timing == SignalTiming.CLOSE
        and execution.fill_timing == FillTiming.NEXT_OPEN
        and execution.price_source == PriceSource.OPEN
        and not execution.allow_partial_fills
        and not execution.allow_short
        and execution.trade_accounting_policy == TradeAccountingPolicy.AVERAGE_COST
    )
    if not supported_execution:
        raise InvalidBacktestRequestError("Unsupported execution configuration")


def _validate_strategy(request: BacktestRequest) -> None:
    try:
        strategy = resolve_strategy(request.strategy)
    except ValueError as exc:
        raise InvalidBacktestRequestError(str(exc)) from exc
    if not strategy.is_v1_parity_compatible:
        raise InvalidBacktestRequestError("Backtest requests require a v1 declarative bar strategy")


def _new_run_id() -> str:
    return str(uuid4())


def _utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
