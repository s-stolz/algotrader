"""Application-layer orchestration for one backtest run."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Mapping

import pandas as pd
from adapters.db_accessor import DatabaseAccessorHistoricalDataAdapter, HistoricalBarDataAdapter
from data.indicator_inputs import needs_source_inputs
from data.indicators import build_feature_frame
from data.market_data import load_market_data, load_market_data_bundle, load_raw_market_data
from data.normalization import normalize_bar_data
from data.warmup import trim_bars_for_execution
from domain.enums import BacktestEngine, DataGranularity
from domain.progress import report_progress
from domain.types import BacktestRequest, BacktestResult
from engines.event_driven import run_event_driven_backtest
from engines.vectorized import run_vectorized_backtest
from strategies.base import StrategyDefinition
from strategies.chart import snapshot_chart_indicators
from strategies.registry import resolve_strategy

from app.equity_replay import descriptor, executable_closes


def run_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition | None = None,
    feature_bars: Mapping[str, pd.DataFrame] | None = None,
    execution_bars: pd.DataFrame | None = None,
) -> BacktestResult:
    """Execute one backtest request using caller-provided bar data."""

    result, _ = _execute_backtest(
        request=request,
        bars=bars,
        strategy=strategy,
        feature_bars=feature_bars,
        execution_bars=execution_bars,
    )
    return result


def _execute_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition | None = None,
    feature_bars: Mapping[str, pd.DataFrame] | None = None,
    execution_bars: pd.DataFrame | None = None,
) -> tuple[BacktestResult, int]:
    report_progress("preparing_indicators")
    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.execution.execution_mode == "orders":
        from app.order_backtest import execute_order_backtest

        started_at = perf_counter()
        result, minute_frame = execute_order_backtest(
            request=request,
            bars=bars,
            strategy=resolved_strategy,
            execution_bars=execution_bars,
            feature_bars=feature_bars,
        )
        return _attach_replay_descriptor(
            request, minute_frame, result, resolved_strategy
        ), _elapsed_ms_since(started_at)
    if resolved_strategy.order_model is not None:
        raise ValueError("Order strategies require execution_mode=orders")

    if request.engine == BacktestEngine.VECTORIZED:
        if request.data_granularity == DataGranularity.BAR:
            prepared_bars = prepare_bars_for_vectorized_execution(
                request=request,
                bars=bars,
                strategy=resolved_strategy,
                feature_bars=feature_bars,
            )
            started_at = perf_counter()
            result = run_vectorized_backtest(
                request=request,
                bars=prepared_bars,
                strategy=resolved_strategy,
            )
            return _attach_replay_descriptor(
                request, prepared_bars, result, resolved_strategy
            ), _elapsed_ms_since(started_at)

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
                feature_bars=feature_bars,
            )
            return _attach_replay_descriptor(
                request, bars, result, resolved_strategy
            ), _elapsed_ms_since(started_at)

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
) -> BacktestResult:
    """Fetch market data and run the requested backtest engine."""

    result, _ = _execute_backtest_with_market_data(
        request=request,
        strategy=strategy,
        exchange=exchange,
        data_adapter=data_adapter,
    )
    return result


def _execute_backtest_with_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition | None = None,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> tuple[BacktestResult, int]:
    report_progress("loading_data")
    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.execution.execution_mode == "orders":
        adapter = data_adapter or DatabaseAccessorHistoricalDataAdapter.for_request(request)
        if needs_source_inputs(resolved_strategy):
            bundle = load_market_data_bundle(
                request=request, strategy=resolved_strategy, exchange=exchange, data_adapter=adapter
            )
            strategy_bars, inputs = bundle.traded_bars, bundle.feature_bars
        else:
            strategy_bars = load_raw_market_data(
                request=request, strategy=resolved_strategy, exchange=exchange, data_adapter=adapter
            )
            inputs = None
        minutes = (
            strategy_bars
            if request.timeframe.upper() == "M1"
            else adapter.fetch_bars(
                symbol=request.symbols[0],
                timeframe="M1",
                start_ms=request.start_ms,
                end_ms=request.end_ms,
                exchange=exchange if exchange is not None else request.exchange,
            )
        )
        return _execute_backtest(
            request=request,
            bars=strategy_bars,
            strategy=resolved_strategy,
            execution_bars=minutes,
            feature_bars=inputs,
        )

    if needs_source_inputs(resolved_strategy):
        bundle = load_market_data_bundle(
            request=request,
            strategy=resolved_strategy,
            exchange=exchange,
            data_adapter=data_adapter,
        )
        return _execute_backtest(
            request=request,
            bars=bundle.traded_bars,
            strategy=resolved_strategy,
            feature_bars=bundle.feature_bars,
        )

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
            return _attach_replay_descriptor(
                request, prepared_bars, result, resolved_strategy
            ), _elapsed_ms_since(started_at)

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
            return _attach_replay_descriptor(
                request, raw_bars, result, resolved_strategy
            ), _elapsed_ms_since(started_at)

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for event-driven execution"
        )

    raise ValueError(f"Unsupported backtest engine '{_engine_value(request.engine)}'")


def _attach_replay_descriptor(
    request: BacktestRequest,
    bars: pd.DataFrame,
    result: BacktestResult,
    strategy: StrategyDefinition,
) -> BacktestResult:
    executable_timestamps = [point.timestamp_ms for point in result.equity_curve]
    normalized = normalize_bar_data(bars=bars, symbol=str(request.symbols[0]))
    bars_by_timestamp = {timestamp: close for timestamp, close in executable_closes(normalized)}
    if len(executable_timestamps) != len(set(executable_timestamps)) or any(
        timestamp not in bars_by_timestamp for timestamp in executable_timestamps
    ):
        raise ValueError("Executable Candle shape differs from the result equity points")
    closes = [(timestamp, bars_by_timestamp[timestamp]) for timestamp in executable_timestamps]
    return replace(
        result,
        replay_descriptor=descriptor(request, closes),
        diagnostics={**result.diagnostics, "chart_indicators": snapshot_chart_indicators(strategy)},
    )


def prepare_bars_for_vectorized_execution(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    feature_bars: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Normalize, feature-enrich, and trim bars for deterministic vectorized execution."""

    if len(request.symbols) != 1:
        raise ValueError("Vectorized runner supports exactly one symbol per run")

    symbol = str(request.symbols[0])
    normalized = normalize_bar_data(bars=bars, symbol=symbol)
    featured = build_feature_frame(
        bars=normalized,
        strategy=strategy,
        timeframe=request.timeframe,
        feature_bars=feature_bars,
    )
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


def _elapsed_ms_since(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


def _engine_value(engine: object) -> str:
    if isinstance(engine, BacktestEngine):
        return engine.value
    return str(engine)
