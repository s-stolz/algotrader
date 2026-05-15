"""Market-data loading orchestration for real-data backtest runs."""

from __future__ import annotations

import pandas as pd
from adapters.db_accessor import (
    DatabaseAccessorHistoricalDataAdapter,
    HistoricalBarDataAdapter,
)
from domain.types import BacktestRequest
from strategies.base import StrategyDefinition

from data.indicators import build_feature_frame
from data.normalization import normalize_bar_data
from data.warmup import (
    compute_fetch_start_ms,
    compute_required_warmup_bars,
    trim_bars_for_execution,
)


def load_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> pd.DataFrame:
    """Fetch and prepare bars for vectorized execution."""

    normalized = load_raw_market_data(
        request=request,
        strategy=strategy,
        exchange=exchange,
        data_adapter=data_adapter,
    )
    featured = build_feature_frame(bars=normalized, strategy=strategy)
    return trim_bars_for_execution(
        bars=featured,
        required_features=strategy.feature_specs,
        start_ms=int(request.start_ms),
        end_ms=int(request.end_ms),
    )


def load_raw_market_data(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> pd.DataFrame:
    """Fetch and normalize raw bars, including any strategy warmup window."""

    if len(request.symbols) != 1:
        raise ValueError("M2 market-data path supports exactly one symbol per run")

    symbol = str(request.symbols[0])
    warmup_bars = compute_required_warmup_bars(strategy)
    fetch_start_ms = compute_fetch_start_ms(
        start_ms=int(request.start_ms),
        timeframe=request.timeframe,
        warmup_bars=warmup_bars,
    )

    adapter = data_adapter or DatabaseAccessorHistoricalDataAdapter()
    raw_bars = adapter.fetch_bars(
        symbol=symbol,
        timeframe=request.timeframe,
        start_ms=fetch_start_ms,
        end_ms=int(request.end_ms),
        exchange=exchange,
    )

    return normalize_bar_data(bars=raw_bars, symbol=symbol)
