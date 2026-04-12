"""Application-layer orchestration for one backtest run."""

from __future__ import annotations

import pandas as pd
from adapters.db_accessor import HistoricalBarDataAdapter
from data.indicators import build_feature_frame
from data.market_data import load_market_data
from data.normalization import normalize_bar_data
from data.warmup import trim_bars_for_execution
from domain.enums import DataGranularity
from domain.types import BacktestRequest, BacktestResult
from engines.vectorized import run_vectorized_backtest
from strategies.base import StrategyDefinition


def run_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> BacktestResult:
    """Execute one backtest request using caller-provided bar data."""

    if request.data_granularity == DataGranularity.BAR:
        prepared_bars = prepare_bars_for_vectorized_execution(
            request=request,
            bars=bars,
            strategy=strategy,
        )
        return run_vectorized_backtest(request=request, bars=prepared_bars, strategy=strategy)

    raise ValueError(
        f"Unsupported data_granularity '{request.data_granularity.value}' for vectorized execution"
    )


def run_backtest_with_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> BacktestResult:
    """Fetch market data through adapter integration and run one vectorized backtest."""

    if request.data_granularity == DataGranularity.BAR:
        prepared_bars = load_market_data(
            request=request,
            strategy=strategy,
            exchange=exchange,
            data_adapter=data_adapter,
        )
        return run_vectorized_backtest(request=request, bars=prepared_bars, strategy=strategy)

    raise ValueError(
        f"Unsupported data_granularity '{request.data_granularity.value}' for vectorized execution"
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
