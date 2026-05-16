"""Application-layer orchestration for one backtest run."""

from __future__ import annotations

from time import perf_counter
from typing import Protocol

import pandas as pd
from adapters.db_accessor import HistoricalBarDataAdapter
from adapters.persistence import BacktestRunSummaryPersistenceAdapter
from data.indicators import build_feature_frame
from data.market_data import load_market_data, load_raw_market_data
from data.normalization import normalize_bar_data
from data.warmup import trim_bars_for_execution
from domain.enums import BacktestEngine, DataGranularity
from domain.types import BacktestRequest, BacktestResult
from engines.event_driven import run_event_driven_backtest
from engines.vectorized import run_vectorized_backtest
from strategies.base import StrategyDefinition
from strategies.registry import resolve_strategy


class BacktestPersistenceAdapter(Protocol):
    """Persistence adapter surface used by app orchestration."""

    def save_run_summary(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult: ...


def run_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition | None = None,
    persistence_adapter: BacktestPersistenceAdapter | None = None,
) -> BacktestResult:
    """Execute one backtest request using caller-provided bar data."""

    result, execution_duration_ms = _run_backtest_without_persistence(
        request=request,
        bars=bars,
        strategy=strategy,
    )
    return _persist_result_if_requested(
        result=result,
        persistence_adapter=persistence_adapter,
        execution_duration_ms=execution_duration_ms,
    )


def _run_backtest_without_persistence(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition | None = None,
) -> tuple[BacktestResult, int]:
    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.engine == BacktestEngine.VECTORIZED:
        if request.data_granularity == DataGranularity.BAR:
            prepared_bars = prepare_bars_for_vectorized_execution(
                request=request,
                bars=bars,
                strategy=resolved_strategy,
            )
            started_at = perf_counter()
            result = run_vectorized_backtest(
                request=request,
                bars=prepared_bars,
                strategy=resolved_strategy,
            )
            return result, _elapsed_ms_since(started_at)

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for vectorized execution"
        )

    if request.engine == BacktestEngine.EVENT_DRIVEN:
        if request.data_granularity == DataGranularity.BAR:
            started_at = perf_counter()
            result = run_event_driven_backtest(
                request=request,
                bars=bars,
                strategy=resolved_strategy,
            )
            return result, _elapsed_ms_since(started_at)

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for event-driven execution"
        )

    raise ValueError(f"Unsupported backtest engine '{_engine_value(request.engine)}'")


def run_backtest_with_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition | None = None,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
    persistence_adapter: BacktestPersistenceAdapter | None = None,
) -> BacktestResult:
    """Fetch market data through adapter integration and run one vectorized backtest."""

    result, execution_duration_ms = _run_backtest_with_market_data_without_persistence(
        request=request,
        strategy=strategy,
        exchange=exchange,
        data_adapter=data_adapter,
    )
    return _persist_result_if_requested(
        result=result,
        persistence_adapter=persistence_adapter,
        execution_duration_ms=execution_duration_ms,
    )


def _run_backtest_with_market_data_without_persistence(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition | None = None,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> tuple[BacktestResult, int]:
    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.engine == BacktestEngine.VECTORIZED:
        if request.data_granularity == DataGranularity.BAR:
            prepared_bars = load_market_data(
                request=request,
                strategy=resolved_strategy,
                exchange=exchange,
                data_adapter=data_adapter,
            )
            started_at = perf_counter()
            result = run_vectorized_backtest(
                request=request,
                bars=prepared_bars,
                strategy=resolved_strategy,
            )
            return result, _elapsed_ms_since(started_at)

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for vectorized execution"
        )

    if request.engine == BacktestEngine.EVENT_DRIVEN:
        if request.data_granularity == DataGranularity.BAR:
            raw_bars = load_raw_market_data(
                request=request,
                strategy=resolved_strategy,
                exchange=exchange,
                data_adapter=data_adapter,
            )
            started_at = perf_counter()
            result = run_event_driven_backtest(
                request=request,
                bars=raw_bars,
                strategy=resolved_strategy,
            )
            return result, _elapsed_ms_since(started_at)

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for event-driven execution"
        )

    raise ValueError(f"Unsupported backtest engine '{_engine_value(request.engine)}'")


def save_backtest_result(
    *,
    result: BacktestResult,
    persistence_adapter: BacktestPersistenceAdapter | None = None,
    execution_duration_ms: int | None = None,
) -> BacktestResult:
    """Persist an already completed backtest result and return metadata on the result."""

    adapter = persistence_adapter or BacktestRunSummaryPersistenceAdapter()
    return adapter.save_run_summary(
        result=result,
        execution_duration_ms=execution_duration_ms,
    )


def prepare_bars_for_vectorized_execution(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> pd.DataFrame:
    """Normalize, feature-enrich, and trim bars for deterministic vectorized execution."""

    if len(request.symbols) != 1:
        raise ValueError("Vectorized runner supports exactly one symbol per run")

    symbol = str(request.symbols[0])
    normalized = normalize_bar_data(bars=bars, symbol=symbol)
    featured = build_feature_frame(bars=normalized, strategy=strategy)
    return trim_bars_for_execution(
        bars=featured,
        required_features=strategy.feature_specs,
        start_ms=int(request.start_ms),
        end_ms=int(request.end_ms),
    )


def _validate_strategy_request_consistency(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
) -> None:
    if request.strategy.strategy_id != strategy.strategy_id:
        raise ValueError(
            "request.strategy.strategy_id must match the provided strategy definition: "
            f"{request.strategy.strategy_id!r} != {strategy.strategy_id!r}"
        )


def _resolve_strategy_for_request(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition | None,
) -> StrategyDefinition:
    if strategy is None:
        return resolve_strategy(request.strategy)

    _validate_strategy_request_consistency(request=request, strategy=strategy)
    return strategy


def _persist_result_if_requested(
    *,
    result: BacktestResult,
    persistence_adapter: BacktestPersistenceAdapter | None,
    execution_duration_ms: int,
) -> BacktestResult:
    if not result.request.persist_result:
        return result

    return save_backtest_result(
        result=result,
        persistence_adapter=persistence_adapter,
        execution_duration_ms=execution_duration_ms,
    )


def _elapsed_ms_since(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


def _engine_value(engine: object) -> str:
    if isinstance(engine, BacktestEngine):
        return engine.value
    return str(engine)
