"""Application-layer orchestration for one backtest run."""

from __future__ import annotations

import pandas as pd
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
    """Execute one backtest request using the configured runtime."""

    if request.data_granularity == DataGranularity.BAR:
        return run_vectorized_backtest(request=request, bars=bars, strategy=strategy)

    raise ValueError(
        f"Unsupported data_granularity '{request.data_granularity.value}' for M1 execution"
    )
