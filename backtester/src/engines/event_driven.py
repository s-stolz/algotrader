"""Minimal sequential bar-mode backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from data.feature_stream import EventDrivenFeatureStream
from data.normalization import normalize_bar_data
from domain.enums import (
    BacktestEngine,
    DataGranularity,
    FillTiming,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)
from domain.types import (
    BacktestRequest,
    BacktestResult,
    BarView,
    ExecutionArrayBundle,
    SignalMatrix,
)
from execution.fills import FillGenerationResult, generate_fills_from_targets
from execution.portfolio import build_equity_curve
from execution.trades import build_trades_from_fills
from reporting.metrics import compute_metrics
from strategies.base import StrategyDefinition


def run_event_driven_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> BacktestResult:
    """Run a single-symbol event-driven bar backtest."""

    _validate_event_driven_request(request=request, strategy=strategy)

    symbol = str(request.symbols[0])
    normalized = normalize_bar_data(bars=bars, symbol=symbol)
    normalized = normalized.loc[normalized["timestamp_ms"] < int(request.end_ms)].copy()
    if normalized.empty:
        raise ValueError("No bars found before request end_ms for event-driven execution")
    normalized.sort_values("timestamp_ms", kind="mergesort", inplace=True)
    normalized.reset_index(drop=True, inplace=True)

    event_targets = _build_event_driven_targets(
        request=request,
        bars=normalized,
        strategy=strategy,
        symbol=symbol,
    )

    fill_result = generate_fills_from_targets(
        symbol=symbol,
        timestamp_ms=event_targets.timestamp_ms,
        open_prices=event_targets.open_prices,
        target_quantity=event_targets.target_quantity,
        gap_policy=request.execution.gap_policy,
        slippage_bps=float(request.execution.slippage_bps),
        commission_bps=float(request.execution.commission_bps),
    )

    equity_curve = build_equity_curve(
        symbol=symbol,
        timestamp_ms=event_targets.timestamp_ms,
        close_prices=event_targets.close_prices,
        executed_delta=fill_result.executed_delta,
        executed_notional=fill_result.executed_notional,
        executed_fees=fill_result.executed_fees,
        initial_capital=request.initial_capital,
    )

    trades = build_trades_from_fills(fill_result.fills)
    metrics = compute_metrics(equity_curve=equity_curve, trades=trades)

    return BacktestResult(
        request=request,
        fills=fill_result.fills,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        diagnostics=_build_diagnostics(
            request=request,
            strategy=strategy,
            symbol=symbol,
            bar_count=len(event_targets.timestamp_ms),
            fill_result=fill_result,
            processed_bar_count=event_targets.processed_bar_count,
            feature_snapshot_count=event_targets.feature_snapshot_count,
            nonzero_signal_count=event_targets.nonzero_signal_count,
        ),
    )


@dataclass(frozen=True)
class _EventDrivenTargets:
    timestamp_ms: list[int]
    open_prices: list[float]
    close_prices: list[float]
    target_quantity: np.ndarray
    processed_bar_count: int
    feature_snapshot_count: int
    nonzero_signal_count: int


def _build_event_driven_targets(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    symbol: str,
) -> _EventDrivenTargets:
    bar_model = strategy.require_v1_parity_model()
    stream = EventDrivenFeatureStream(
        strategy=strategy,
        symbol=symbol,
        timeframe=request.timeframe,
    )

    start_ms = int(request.start_ms)
    end_ms = int(request.end_ms)
    bootstrap_bars = bars.loc[bars["timestamp_ms"] < start_ms]
    tradable_bars = bars.loc[(bars["timestamp_ms"] >= start_ms) & (bars["timestamp_ms"] < end_ms)]

    timestamps: list[int] = []
    opens: list[float] = []
    closes: list[float] = []
    signals: list[int] = []
    previous_features: dict[str, float] | None = None
    processed_bar_count = len(bars)
    feature_snapshot_count = 0

    for row in bootstrap_bars.itertuples(index=False):
        bar = _bar_from_row(row)
        snapshot = stream.update(bar)
        if snapshot is None:
            continue
        feature_snapshot_count += 1
        previous_features = dict(snapshot.features)

    if strategy.indicator_requirements and previous_features is None:
        required_features = _format_required_indicator_features(strategy)
        raise ValueError(
            "Event-driven bar bootstrap has insufficient warmup before start_ms "
            f"{start_ms} for strategy '{strategy.strategy_id}'; required feature(s): "
            f"{required_features}"
        )

    for row in tradable_bars.itertuples(index=False):
        bar = _bar_from_row(row)
        snapshot = stream.update(bar)
        if snapshot is None:
            required_features = _format_required_indicator_features(strategy)
            raise ValueError(
                "Event-driven bar runtime produced an incomplete feature snapshot at "
                f"timestamp_ms {bar.timestamp_ms}; required feature(s): {required_features}"
            )
        feature_snapshot_count += 1
        signal = bar_model.evaluate_sequential_signal(
            previous=previous_features,
            current=snapshot.features,
        )
        previous_features = dict(snapshot.features)

        timestamps.append(int(snapshot.timestamp_ms))
        opens.append(float(bar.open))
        closes.append(float(bar.close))
        signals.append(int(signal))

    if not timestamps:
        raise ValueError(
            "No executable bars remain after warmup/feature trimming for the requested window"
        )

    signal_matrix = SignalMatrix(
        timestamp_ms=timestamps,
        signals_by_symbol={symbol: signals},
    )
    execution_targets = bar_model.build_positions(signal_matrix)
    execution_targets = _apply_execution_transforms(
        strategy=strategy,
        execution_targets=execution_targets,
    )

    return _EventDrivenTargets(
        timestamp_ms=timestamps,
        open_prices=opens,
        close_prices=closes,
        target_quantity=_extract_target_values(
            execution_targets=execution_targets,
            symbol=symbol,
            expected_size=len(timestamps),
        ),
        processed_bar_count=processed_bar_count,
        feature_snapshot_count=feature_snapshot_count,
        nonzero_signal_count=sum(1 for signal in signals if signal != 0),
    )


def _format_required_indicator_features(strategy: StrategyDefinition) -> str:
    feature_names = [requirement.feature_name for requirement in strategy.indicator_requirements]
    if not feature_names:
        return "none"
    return ", ".join(feature_names)


def _validate_event_driven_request(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
) -> None:
    execution = request.execution
    constraints = (
        (
            request.engine == BacktestEngine.EVENT_DRIVEN,
            "Event-driven engine requires engine=event_driven",
        ),
        (
            request.data_granularity == DataGranularity.BAR,
            "Event-driven engine supports bar data only",
        ),
        (
            len(request.symbols) == 1,
            "Event-driven engine supports exactly one symbol per run",
        ),
        (
            strategy.is_v1_parity_compatible,
            "Event-driven engine supports v1 declarative bar strategies only",
        ),
        (
            execution.signal_timing == SignalTiming.CLOSE,
            "Event-driven engine supports signal_timing=close only",
        ),
        (
            not execution.allow_short,
            "Event-driven engine does not support allow_short=True",
        ),
        (
            execution.fill_timing == FillTiming.NEXT_OPEN,
            "Event-driven engine supports fill_timing=next_open only",
        ),
        (
            execution.price_source == PriceSource.OPEN,
            "Event-driven engine supports price_source=open only",
        ),
        (
            not execution.allow_partial_fills,
            "Event-driven engine does not support allow_partial_fills=True",
        ),
        (
            execution.trade_accounting_policy == TradeAccountingPolicy.AVERAGE_COST,
            "Event-driven engine supports trade_accounting_policy=average_cost only",
        ),
    )
    for is_valid, message in constraints:
        if not is_valid:
            raise ValueError(message)


def _apply_execution_transforms(
    *,
    strategy: StrategyDefinition,
    execution_targets: ExecutionArrayBundle,
) -> ExecutionArrayBundle:
    transformed = execution_targets
    if strategy.sizing_model is not None:
        transformed = strategy.sizing_model(transformed)
    for risk_rule in strategy.risk_rules:
        transformed = risk_rule(transformed)
    return transformed


def _extract_target_values(
    *,
    execution_targets: ExecutionArrayBundle,
    symbol: str,
    expected_size: int,
) -> np.ndarray:
    target = execution_targets.target_quantity_by_symbol.get(symbol)
    if target is None:
        raise ValueError(f"Strategy did not produce execution targets for symbol {symbol}")

    target_values = np.asarray(target, dtype=np.float64)
    if target_values.size != expected_size:
        raise ValueError(
            f"Strategy target quantity length must match executable bar count for symbol {symbol}"
        )
    if not np.isfinite(target_values).all():
        raise ValueError(f"Strategy produced non-finite target quantities for symbol {symbol}")
    if np.any(target_values < 0.0):
        raise ValueError(
            "Event-driven engine is long-only and requires non-negative target quantities "
            f"for symbol {symbol}"
        )
    return target_values


def _build_diagnostics(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    symbol: str,
    bar_count: int,
    fill_result: FillGenerationResult,
    processed_bar_count: int,
    feature_snapshot_count: int,
    nonzero_signal_count: int,
) -> dict[str, float | int | str]:
    return {
        "engine": "event_driven",
        "bars": int(bar_count),
        "symbol": symbol,
        "strategy_id": strategy.strategy_id,
        "processed_bar_count": int(processed_bar_count),
        "feature_snapshot_count": int(feature_snapshot_count),
        "executable_bar_count": int(bar_count),
        "nonzero_signal_count": int(nonzero_signal_count),
        "fill_timing": request.execution.fill_timing.value,
        "gap_policy": request.execution.gap_policy.value,
        "commission_bps": float(request.execution.commission_bps),
        "slippage_bps": float(request.execution.slippage_bps),
        "total_fees": float(fill_result.executed_fees.sum()),
        "total_slippage_cost": float(fill_result.total_slippage_cost),
        "invalid_open_count": int(fill_result.invalid_open_count),
        "deferred_delta_count": int(fill_result.deferred_delta_count),
        "expired_delta_count": int(fill_result.expired_delta_count),
        "executed_deferred_count": int(fill_result.executed_deferred_count),
        "tail_expired_delta_count": int(fill_result.tail_expired_delta_count),
    }


def _bar_from_row(row: Any) -> BarView:
    return BarView(
        timestamp_ms=int(row.timestamp_ms),
        symbol=str(row.symbol),
        open=float(row.open),
        high=float(row.high),
        low=float(row.low),
        close=float(row.close),
        volume=float(row.volume),
    )
