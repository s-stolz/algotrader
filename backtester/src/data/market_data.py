"""Market-data loading orchestration for real-data backtest runs."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from adapters.db_accessor import (
    DatabaseAccessorHistoricalDataAdapter,
    HistoricalBarDataAdapter,
)
from domain.progress import report_progress
from domain.types import BacktestRequest
from indicator_engine import get_registry
from strategies.base import StrategyDefinition

from data.indicator_inputs import needs_source_inputs
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

    if needs_source_inputs(strategy):
        bundle = load_market_data_bundle(
            request=request,
            strategy=strategy,
            exchange=exchange,
            data_adapter=data_adapter,
        )
        report_progress("preparing_indicators")
        featured = build_feature_frame(
            bars=bundle.traded_bars,
            strategy=strategy,
            timeframe=request.timeframe,
            feature_bars=bundle.feature_bars,
        )
        return trim_bars_for_execution(
            bars=featured,
            required_features=strategy.feature_specs,
            start_ms=int(request.start_ms),
            end_ms=int(request.end_ms),
        )

    normalized = load_raw_market_data(
        request=request,
        strategy=strategy,
        exchange=exchange,
        data_adapter=data_adapter,
    )
    report_progress("preparing_indicators")
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

    adapter = data_adapter or DatabaseAccessorHistoricalDataAdapter.for_request(request)
    resolved_exchange = exchange if exchange is not None else request.exchange
    raw_bars = adapter.fetch_bars(
        symbol=symbol,
        timeframe=request.timeframe,
        start_ms=fetch_start_ms,
        end_ms=int(request.end_ms),
        exchange=resolved_exchange,
    )

    normalized = normalize_bar_data(bars=raw_bars, symbol=symbol)
    return _recover_warmup_history(
        normalized=normalized,
        request=request,
        adapter=adapter,
        exchange=resolved_exchange,
        warmup_bars=warmup_bars,
        history_end_ms=fetch_start_ms,
    )


def _recover_warmup_history(
    *,
    normalized: pd.DataFrame,
    request: BacktestRequest,
    adapter: HistoricalBarDataAdapter,
    exchange: str | None,
    warmup_bars: int,
    history_end_ms: int,
) -> pd.DataFrame:
    """Supplement normalized bars until warmup is covered or older history runs out."""

    symbol = str(request.symbols[0])
    # Warmup includes the first executable candle. Recover missing predecessors
    # by count so market closures do not limit how far back history can reach.
    while (
        missing_bars := warmup_bars
        - 1
        - len(normalized.loc[normalized["timestamp_ms"] < int(request.start_ms)])
    ) > 0:
        prior = adapter.fetch_bars(
            symbol=symbol,
            timeframe=request.timeframe,
            start_ms=None,
            end_ms=history_end_ms,
            exchange=exchange,
            limit=missing_bars,
        )
        if prior.empty:
            break
        prior = prior.loc[prior["timestamp_ms"] < history_end_ms]
        if prior.empty:
            break
        history_end_ms = int(prior["timestamp_ms"].min())
        if "symbol" not in prior.columns:
            prior = prior.assign(symbol=symbol)
        normalized = normalize_bar_data(
            bars=pd.concat([prior, normalized], ignore_index=True), symbol=symbol
        )

    return normalized


@dataclass(frozen=True)
class BacktestMarketData:
    traded_bars: pd.DataFrame
    feature_bars: dict[str, pd.DataFrame]


def load_market_data_bundle(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    exchange: str | None = None,
    data_adapter: HistoricalBarDataAdapter | None = None,
) -> BacktestMarketData:
    """Fetch deduplicated indicator sources without adding executable symbols."""
    if len(request.symbols) != 1:
        raise ValueError("Market data requires exactly one traded symbol")
    symbol = str(request.symbols[0])
    adapter = data_adapter or DatabaseAccessorHistoricalDataAdapter.for_request(request)
    sources = {symbol}
    start = compute_fetch_start_ms(
        start_ms=int(request.start_ms),
        timeframe=request.timeframe,
        warmup_bars=compute_required_warmup_bars(strategy) + 1,
    )
    predecessor_count = 0
    for requirement in strategy.indicator_requirements:
        spec = get_registry().get(requirement.indicator_id).spec
        sources.update(spec.required_assets or [symbol])
        plan = spec.plan_history(
            start_ms=int(request.start_ms), params=dict(requirement.parameters)
        )
        start = min(start, plan.start_ms)
        if requirement.capture_at_utc_minute is not None:
            day_start = int(request.start_ms) // 86_400_000 * 86_400_000
            start = min(
                start,
                compute_fetch_start_ms(
                    start_ms=day_start,
                    timeframe=request.timeframe,
                    warmup_bars=compute_required_warmup_bars(strategy) + 1,
                ),
            )
        predecessor_count = max(predecessor_count, plan.predecessor_bars)
    frames = {}
    for source in sorted(sources):
        resolved_exchange = exchange if exchange is not None else request.exchange
        frame = adapter.fetch_bars(
            symbol=source,
            timeframe=request.timeframe,
            exchange=resolved_exchange,
            start_ms=start,
            end_ms=int(request.end_ms),
        )
        if predecessor_count:
            prior = adapter.fetch_bars(
                symbol=source,
                timeframe=request.timeframe,
                exchange=resolved_exchange,
                start_ms=None,
                end_ms=start,
                limit=predecessor_count,
            )
            frame = pd.concat([prior, frame], ignore_index=True)
        frames[source] = frame
    traded = normalize_bar_data(bars=frames[symbol], symbol=symbol)
    return BacktestMarketData(traded_bars=traded, feature_bars=frames)
