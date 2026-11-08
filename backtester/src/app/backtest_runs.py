"""Application use cases for durable backtest run submission and retrieval."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Protocol

from adapters.db_accessor import DatabaseAccessorHistoricalDataAdapter, HistoricalBarDataAdapter
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
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRunCancellation,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
)
from strategies.registry import (
    InvalidParameterCombinationError,
    InvalidStrategyParameterError,
    StrategyVersionUnavailableError,
    resolve_strategy_and_parameters,
)

from app.equity_replay import (
    ReplayUnavailableError,
    executable_closes,
    replay,
    sample,
    valid_descriptor,
)


class BacktestRunRepository(Protocol):
    """Persistence boundary used by durable run application workflows."""

    def get(self, run_id: str) -> BacktestRunRecord | None: ...

    def cancel(self, run_id: str) -> BacktestRunCancellation: ...

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]: ...

    def get_fills(self, run_id: str) -> list[BacktestFillRecord]: ...

    def get_trades(self, run_id: str) -> list[BacktestTradeRecord]: ...


class InvalidBacktestRequestError(ValueError):
    """Raised when a deterministic submission rule is violated."""


class BacktestRunNotFoundError(LookupError):
    """Raised when a requested durable run does not exist."""


class BacktestRunConflictError(RuntimeError):
    """Raised when an operation conflicts with the current run lifecycle."""


class BacktestRunPersistenceError(RuntimeError):
    """Raised when the durable persistence boundary cannot complete an operation."""


class BacktestCandleUnavailableError(RuntimeError):
    """Current Candle storage cannot be read."""


class BacktestRunService:
    """Coordinates durable run lifecycle operations without executing backtests."""

    def __init__(
        self,
        *,
        repository: BacktestRunRepository,
        data_adapter: HistoricalBarDataAdapter | None = None,
    ) -> None:
        self._repository = repository
        self._data_adapter = data_adapter

    def get(self, run_id: str) -> BacktestRunRecord:
        try:
            run = self._repository.get(run_id)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        if run is None:
            raise BacktestRunNotFoundError(f"Backtest run not found: {run_id}")
        return run

    def cancel(self, run_id: str) -> BacktestRunRecord:
        try:
            cancellation = self._repository.cancel(run_id)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        if cancellation.outcome == "not_found":
            raise BacktestRunNotFoundError(f"Backtest run not found: {run_id}")
        if cancellation.outcome == "conflict":
            raise BacktestRunConflictError("Terminal backtest run cannot be cancelled")
        if cancellation.run is None:
            raise BacktestRunPersistenceError("Backtest persistence unavailable")
        return cancellation.run

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        if (
            query.submitted_from_ms is not None
            and query.submitted_to_ms is not None
            and query.submitted_from_ms > query.submitted_to_ms
        ):
            raise InvalidBacktestRequestError(
                "submitted_from_ms must be less than or equal to submitted_to_ms"
            )
        try:
            return self._repository.list(query)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc

    def get_fills(self, run_id: str) -> list[BacktestFillRecord]:
        self.get(run_id)
        try:
            return self._repository.get_fills(run_id)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc

    def get_equity_curve(  # noqa: C901
        self, run_id: str, max_points: int = 2000
    ) -> dict[str, object]:
        if not 100 <= max_points <= 10000:
            raise ValueError("max_points must be between 100 and 10000")
        run = self.get(run_id)
        if run.status != BacktestRunStatus.SUCCEEDED:
            raise BacktestRunConflictError("Equity Replay requires a successful run")
        if run.replay_descriptor is None:
            return _unavailable_curve("replay_metadata_missing")
        request = run.request_snapshot.to_request()
        saved = run.replay_descriptor
        if (
            len(request.symbols) != 1
            or request.data_granularity != DataGranularity.BAR
            or not valid_descriptor(saved)
        ):
            return _unavailable_curve("unsupported_replay_shape")
        adapter = self._data_adapter or DatabaseAccessorHistoricalDataAdapter()
        try:
            bars = adapter.fetch_bars(
                symbol=request.symbols[0],
                timeframe=(
                    "M1" if request.execution.execution_mode == "orders" else request.timeframe
                ),
                start_ms=request.start_ms,
                end_ms=request.end_ms,
                exchange=request.exchange,
            )
        except (ValueError, TypeError, KeyError):
            return _unavailable_curve("unsupported_replay_shape")
        except Exception as exc:
            raise BacktestCandleUnavailableError("Candle service unavailable") from exc
        try:
            if request.execution.execution_mode == "orders":
                from data.order_bars import minute_bars

                bars = minute_bars(request, bars)
            closes = executable_closes(bars, first_timestamp_ms=int(saved["first_timestamp_ms"]))
            fills = self._repository.get_fills(run_id)
            points = replay(request, saved, closes, fills)
        except ReplayUnavailableError as exc:
            return _unavailable_curve(str(exc))
        except (KeyError, TypeError, ValueError, OverflowError):
            return _unavailable_curve("unsupported_replay_shape")
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        returned = sample(points, max_points)
        return {
            "availability": "exact",
            "reason": None,
            "source_point_count": len(points),
            "returned_point_count": len(returned),
            "sampled": len(returned) != len(points),
            "equity_curve": returned,
        }

    def get_trades(self, run_id: str) -> list[BacktestTradeRecord]:
        self.get(run_id)
        try:
            return self._repository.get_trades(run_id)
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc


def _validate_submission(request: BacktestRequest) -> BacktestRequest:
    _validate_request_shape(request)
    _validate_execution(request)
    return _validate_strategy(request)


def _validate_request_shape(request: BacktestRequest) -> None:
    if not _is_epoch_millisecond(request.start_ms) or not _is_epoch_millisecond(request.end_ms):
        raise InvalidBacktestRequestError("start_ms and end_ms must be integer epoch milliseconds")
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
        and execution.trade_accounting_policy == TradeAccountingPolicy.AVERAGE_COST
    )
    if not supported_execution:
        raise InvalidBacktestRequestError("Unsupported execution configuration")


def _validate_strategy(request: BacktestRequest) -> BacktestRequest:
    if request.strategy.strategy_version is None:
        raise InvalidBacktestRequestError("strategy_version is required")
    try:
        strategy, resolved = resolve_strategy_and_parameters(request.strategy)
    except (
        InvalidParameterCombinationError,
        InvalidStrategyParameterError,
        StrategyVersionUnavailableError,
    ):
        raise
    except ValueError as exc:
        raise InvalidBacktestRequestError(str(exc)) from exc
    if request.execution.execution_mode == "orders":
        if strategy.order_model is None:
            raise InvalidBacktestRequestError("Order execution requires an order strategy")
        if strategy.order_model.requires_min_move and request.market_min_move is None:
            raise InvalidBacktestRequestError(
                "Selected market requires a positive min_move for tick protection"
            )
        if strategy.sizing_model is not None or strategy.risk_rules:
            raise InvalidBacktestRequestError(
                "Target transforms cannot be used with explicit orders"
            )
        return replace(request, strategy=resolved)
    if strategy.order_model is not None:
        raise InvalidBacktestRequestError("Order strategies require execution_mode=orders")
    if not strategy.is_v1_parity_compatible:
        raise InvalidBacktestRequestError("Backtest requests require a v1 declarative bar strategy")
    return replace(request, strategy=resolved)


def _is_epoch_millisecond(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _unavailable_curve(reason: str) -> dict[str, object]:
    return {
        "availability": "unavailable",
        "reason": reason,
        "source_point_count": 0,
        "returned_point_count": 0,
        "sampled": False,
        "equity_curve": [],
    }
