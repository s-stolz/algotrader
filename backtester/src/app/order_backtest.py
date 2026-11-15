"""Prepare two-resolution inputs and dispatch explicit order strategies."""

from typing import Mapping

import pandas as pd
from data.order_inputs import prepare_order_inputs
from domain.enums import BacktestEngine
from domain.types import BacktestRequest, BacktestResult
from engines.order_event_driven import run_order_event_driven
from engines.order_vectorized import run_order_vectorized
from strategies.base import StrategyDefinition


def execute_order_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    execution_bars: pd.DataFrame | None,
    feature_bars: Mapping[str, pd.DataFrame] | None = None,
) -> tuple[BacktestResult, pd.DataFrame]:
    featured, minutes = prepare_order_inputs(
        request=request,
        bars=bars,
        strategy=strategy,
        execution_bars=execution_bars,
        feature_bars=feature_bars,
    )
    if request.engine == BacktestEngine.VECTORIZED:
        result = run_order_vectorized(
            request=request, strategy_bars=featured, execution_bars=minutes, strategy=strategy
        )
    elif request.engine == BacktestEngine.EVENT_DRIVEN:
        result = run_order_event_driven(
            request=request, strategy_bars=featured, execution_bars=minutes, strategy=strategy
        )
    else:
        raise ValueError("Unsupported backtest engine")
    return result, minutes
