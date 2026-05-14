"""Application-layer orchestration for one backtest run."""

from __future__ import annotations

import pandas as pd
from adapters.db_accessor import HistoricalBarDataAdapter
from data.indicators import build_feature_frame
from data.market_data import load_market_data
from data.normalization import normalize_bar_data
from data.warmup import trim_bars_for_execution
from domain.enums import BacktestEngine, DataGranularity
from domain.types import BacktestRequest, BacktestResult
from engines.vectorized import run_vectorized_backtest
from strategies.base import StrategyDefinition
from strategies.registry import resolve_strategy


def run_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition | None = None,
) -> BacktestResult:
    """Execute one backtest request using caller-provided bar data."""

    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.engine == BacktestEngine.VECTORIZED:
        if request.data_granularity == DataGranularity.BAR:
            prepared_bars = prepare_bars_for_vectorized_execution(
                request=request,
                bars=bars,
                strategy=resolved_strategy,
            )
            return run_vectorized_backtest(
                request=request,
                bars=prepared_bars,
                strategy=resolved_strategy,
            )

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for vectorized execution"
        )

    if request.engine == BacktestEngine.EVENT_DRIVEN:
        raise NotImplementedError("event_driven engine is not implemented yet")

    raise ValueError(f"Unsupported backtest engine '{_engine_value(request.engine)}'")


def run_backtest_with_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition | None = None,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> BacktestResult:
    """Fetch market data through adapter integration and run one vectorized backtest."""

    resolved_strategy = _resolve_strategy_for_request(request=request, strategy=strategy)

    if request.engine == BacktestEngine.VECTORIZED:
        if request.data_granularity == DataGranularity.BAR:
            prepared_bars = load_market_data(
                request=request,
                strategy=resolved_strategy,
                exchange=exchange,
                data_adapter=data_adapter,
            )
            return run_vectorized_backtest(
                request=request,
                bars=prepared_bars,
                strategy=resolved_strategy,
            )

        raise ValueError(
            f"Unsupported data_granularity '{request.data_granularity.value}' "
            "for vectorized execution"
        )

    if request.engine == BacktestEngine.EVENT_DRIVEN:
        raise NotImplementedError("event_driven engine is not implemented yet")

    raise ValueError(f"Unsupported backtest engine '{_engine_value(request.engine)}'")


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


def _engine_value(engine: object) -> str:
    if isinstance(engine, BacktestEngine):
        return engine.value
    return str(engine)
