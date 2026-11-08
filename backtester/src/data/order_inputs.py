"""Validate and prepare strategy and execution inputs for order engines."""

from typing import Mapping

import pandas as pd
from domain.enums import DataGranularity
from domain.types import BacktestRequest
from strategies.base import StrategyDefinition

from data.indicators import build_feature_frame
from data.normalization import normalize_bar_data
from data.order_bars import close_timestamps, minute_bars
from data.warmup import trim_bars_for_execution


def prepare_order_inputs(  # noqa: C901
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    execution_bars: pd.DataFrame | None,
    feature_bars: Mapping[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(request.symbols) != 1 or request.data_granularity != DataGranularity.BAR:
        raise ValueError("Order execution requires single-symbol bar data")
    if request.execution.allow_partial_fills:
        raise ValueError("Liquidity-based partial order fills are not supported")
    if strategy.order_model is None:
        raise ValueError("Order execution requires an order strategy")
    if strategy.order_model.requires_min_move and request.market_min_move is None:
        raise ValueError("Selected market requires a positive min_move for tick protection")
    if strategy.sizing_model is not None or strategy.risk_rules:
        raise ValueError("Target transforms cannot be used with explicit orders")
    if request.start_ms % 60_000 or request.end_ms % 60_000:
        raise ValueError("Order run boundaries must align to minutes")
    if execution_bars is None:
        if request.timeframe.upper() != "M1":
            raise ValueError("Higher-timeframe order strategies require explicit M1 execution_bars")
        execution_bars = bars
    normalized = normalize_bar_data(bars=bars, symbol=request.symbols[0])
    featured = build_feature_frame(
        bars=normalized, strategy=strategy, timeframe=request.timeframe, feature_bars=feature_bars
    )
    featured = trim_bars_for_execution(
        bars=featured,
        required_features=strategy.feature_specs,
        start_ms=request.start_ms,
        end_ms=request.end_ms,
    )
    featured = featured.loc[
        pd.Series(close_timestamps(featured, request.timeframe), index=featured.index)
        <= request.end_ms
    ].reset_index(drop=True)
    if featured.empty:
        raise ValueError("No completed strategy candles remain after warmup")
    minutes = minute_bars(request, execution_bars)
    minutes = minutes.loc[minutes.timestamp_ms >= int(featured.timestamp_ms.iloc[0])].reset_index(
        drop=True
    )
    if minutes.empty:
        raise ValueError("No minute execution data remains after warmup")
    return featured, minutes
