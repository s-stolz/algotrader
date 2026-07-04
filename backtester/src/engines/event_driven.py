"""Minimal sequential bar-mode backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NoReturn

import numpy as np
import pandas as pd
from data.feature_stream import EventDrivenFeatureStream
from data.normalization import normalize_bar_data
from domain.enums import (
    BacktestEngine,
    DataGranularity,
    ExitReason,
    FillTiming,
    GapPolicy,
    IntrabarExitPolicy,
    OrderSide,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)
from domain.types import (
    BacktestRequest,
    BacktestResult,
    BarView,
    ExecutionArrayBundle,
    Fill,
    PortfolioSnapshot,
)
from execution.fills import FillGenerationResult
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

    run_result = _run_event_driven_loop(
        request=request,
        bars=normalized,
        strategy=strategy,
        symbol=symbol,
    )

    equity_curve = run_result.equity_curve
    trades = build_trades_from_fills(run_result.fill_result.fills)
    metrics = compute_metrics(equity_curve=equity_curve, trades=trades)

    return BacktestResult(
        request=request,
        fills=run_result.fill_result.fills,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        diagnostics=_build_diagnostics(
            request=request,
            strategy=strategy,
            symbol=symbol,
            bar_count=len(equity_curve),
            fill_result=run_result.fill_result,
            processed_bar_count=run_result.processed_bar_count,
            feature_snapshot_count=run_result.feature_snapshot_count,
            nonzero_signal_count=run_result.nonzero_signal_count,
        ),
    )


@dataclass(frozen=True)
class _SequentialRunResult:
    equity_curve: list[PortfolioSnapshot]
    fill_result: FillGenerationResult
    processed_bar_count: int
    feature_snapshot_count: int
    nonzero_signal_count: int


@dataclass
class _PendingDelta:
    quantity: float
    deferred: bool = False


@dataclass
class _SequentialRuntimeState:
    initial_capital: float
    cash: float = field(init=False)
    cash_adjustment: float = 0.0
    raw_desired_target: float = 0.0
    desired_target: float = 0.0
    actual_position: float = 0.0
    entry_price: float | None = None
    pending: list[_PendingDelta] = field(default_factory=list)
    executed_delta: list[float] = field(default_factory=list)
    executed_notional: list[float] = field(default_factory=list)
    executed_fees: list[float] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    total_slippage_cost: float = 0.0
    invalid_open_count: int = 0
    deferred_delta_count: int = 0
    expired_delta_count: int = 0
    executed_deferred_count: int = 0
    intrabar_ambiguous_bar_count: int = 0

    def __post_init__(self) -> None:
        self.cash = float(self.initial_capital)

    def start_bar(self) -> int:
        self.executed_delta.append(0.0)
        self.executed_notional.append(0.0)
        self.executed_fees.append(0.0)
        return len(self.executed_delta) - 1

    def finish_bar(self, *, symbol: str, timestamp_ms: int, close_price: float) -> None:
        position = float(self.actual_position)
        self.snapshots.append(
            PortfolioSnapshot(
                timestamp_ms=timestamp_ms,
                cash=float(self.cash),
                equity=float(self.cash + (position * close_price)),
                positions={symbol: position} if position != 0.0 else {},
            )
        )


def _run_event_driven_loop(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    symbol: str,
) -> _SequentialRunResult:
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

    previous_features: dict[str, float] | None = None
    processed_bar_count = len(bars)
    feature_snapshot_count = 0
    nonzero_signal_count = 0
    state = _SequentialRuntimeState(initial_capital=float(request.initial_capital))

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
        bar_index = state.start_bar()
        protective_exit = bar_model.protective_exit

        _execute_pending_at_open(
            state=state,
            symbol=symbol,
            bar_index=bar_index,
            timestamp_ms=int(bar.timestamp_ms),
            raw_open=float(bar.open),
            stop_loss_pct=protective_exit.stop_loss_pct,
            take_profit_pct=protective_exit.take_profit_pct,
            gap_policy=request.execution.gap_policy,
            slippage_bps=float(request.execution.slippage_bps),
            commission_bps=float(request.execution.commission_bps),
        )

        _execute_protective_exit_if_triggered(
            state=state,
            symbol=symbol,
            bar_index=bar_index,
            timestamp_ms=int(bar.timestamp_ms),
            raw_open=float(bar.open),
            high_price=float(bar.high),
            low_price=float(bar.low),
            stop_loss_pct=protective_exit.stop_loss_pct,
            take_profit_pct=protective_exit.take_profit_pct,
            intrabar_exit_policy=request.execution.intrabar_exit_policy,
            slippage_bps=float(request.execution.slippage_bps),
            commission_bps=float(request.execution.commission_bps),
        )

        snapshot = stream.update(bar)
        if snapshot is None:
            _raise_runtime_invalid_feature_snapshot(
                strategy=strategy,
                symbol=symbol,
                timestamp_ms=int(bar.timestamp_ms),
            )
        feature_snapshot_count += 1
        signal = bar_model.evaluate_sequential_signal(
            previous=previous_features,
            current=snapshot.features,
        )
        previous_features = dict(snapshot.features)
        if signal != 0:
            nonzero_signal_count += 1

        _queue_target_delta_from_signal(
            state=state,
            strategy=strategy,
            bar_model=bar_model,
            symbol=symbol,
            timestamp_ms=int(snapshot.timestamp_ms),
            signal=int(signal),
        )

        state.finish_bar(
            symbol=symbol,
            timestamp_ms=int(bar.timestamp_ms),
            close_price=float(bar.close),
        )

    if not state.snapshots:
        raise ValueError(
            "No executable bars remain after warmup/feature trimming for the requested window"
        )

    return _SequentialRunResult(
        equity_curve=state.snapshots,
        fill_result=_build_fill_generation_result(state),
        processed_bar_count=processed_bar_count,
        feature_snapshot_count=feature_snapshot_count,
        nonzero_signal_count=nonzero_signal_count,
    )


def _execute_pending_at_open(
    *,
    state: _SequentialRuntimeState,
    symbol: str,
    bar_index: int,
    timestamp_ms: int,
    raw_open: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    gap_policy: GapPolicy,
    slippage_bps: float,
    commission_bps: float,
) -> None:
    pending_total = _pending_total(state.pending)
    if pending_total == 0.0:
        state.pending.clear()
        return

    if _is_valid_open(raw_open):
        _record_pending_fill(
            state=state,
            symbol=symbol,
            bar_index=bar_index,
            timestamp_ms=timestamp_ms,
            pending_total=pending_total,
            raw_open=raw_open,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            slippage_bps=slippage_bps,
            commission_bps=commission_bps,
        )
        return

    _handle_invalid_open(
        state=state,
        gap_policy=gap_policy,
        bar_index=bar_index,
        timestamp_ms=timestamp_ms,
    )


def _record_pending_fill(
    *,
    state: _SequentialRuntimeState,
    symbol: str,
    bar_index: int,
    timestamp_ms: int,
    pending_total: float,
    raw_open: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    slippage_bps: float,
    commission_bps: float,
) -> None:
    exit_reason = _pending_exit_reason_at_open(
        state=state,
        pending_total=pending_total,
        raw_open=raw_open,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )
    _record_fill(
        state=state,
        symbol=symbol,
        bar_index=bar_index,
        timestamp_ms=timestamp_ms,
        quantity_delta=pending_total,
        raw_execution_price=raw_open,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
        exit_reason=exit_reason,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )
    state.executed_deferred_count += sum(
        1 for item in state.pending if item.deferred and item.quantity != 0.0
    )
    state.pending.clear()


def _execute_protective_exit_if_triggered(
    *,
    state: _SequentialRuntimeState,
    symbol: str,
    bar_index: int,
    timestamp_ms: int,
    raw_open: float,
    high_price: float,
    low_price: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    intrabar_exit_policy: IntrabarExitPolicy,
    slippage_bps: float,
    commission_bps: float,
) -> None:
    if stop_loss_pct is None and take_profit_pct is None:
        return

    protective_exit = _protective_exit_fill_price(
        raw_open=raw_open,
        high_price=high_price,
        low_price=low_price,
        entry_price=state.entry_price,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        actual_position=state.actual_position,
        timestamp_ms=timestamp_ms,
        intrabar_exit_policy=intrabar_exit_policy,
    )
    if protective_exit is None:
        return

    if protective_exit.ambiguous:
        state.intrabar_ambiguous_bar_count += 1
    _record_fill(
        state=state,
        symbol=symbol,
        bar_index=bar_index,
        timestamp_ms=timestamp_ms,
        quantity_delta=-float(state.actual_position),
        raw_execution_price=protective_exit.fill_price,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
        exit_reason=protective_exit.exit_reason,
    )
    state.raw_desired_target = 0.0
    state.desired_target = 0.0
    state.pending.clear()


def _record_fill(
    *,
    state: _SequentialRuntimeState,
    symbol: str,
    bar_index: int,
    timestamp_ms: int,
    quantity_delta: float,
    raw_execution_price: float,
    slippage_bps: float,
    commission_bps: float,
    exit_reason: ExitReason | None,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> Fill:
    side = OrderSide.BUY if quantity_delta > 0.0 else OrderSide.SELL
    quantity = abs(quantity_delta)
    execution_price = _apply_slippage(
        raw_open=raw_execution_price,
        side=side,
        slippage_bps=slippage_bps,
    )
    fee = quantity * execution_price * (commission_bps / 10_000.0)
    fill = Fill(
        timestamp_ms=timestamp_ms,
        symbol=symbol,
        quantity=quantity,
        price=execution_price,
        side=side,
        fees=float(fee),
        exit_reason=exit_reason,
        stop_loss_price=_planned_stop_loss_price(
            entry_price=execution_price,
            side=side,
            stop_loss_pct=stop_loss_pct,
        ),
        take_profit_price=_planned_take_profit_price(
            entry_price=execution_price,
            side=side,
            take_profit_pct=take_profit_pct,
        ),
    )

    previous_position = float(state.actual_position)
    state.fills.append(fill)
    state.executed_delta[bar_index] += quantity_delta
    state.executed_notional[bar_index] += quantity_delta * execution_price
    state.executed_fees[bar_index] += float(fee)
    state.cash_adjustment += -(quantity_delta * execution_price) - float(fee)
    state.cash = float(state.initial_capital + state.cash_adjustment)
    state.actual_position += quantity_delta
    state.total_slippage_cost += quantity * abs(execution_price - raw_execution_price)

    if quantity_delta > 0.0:
        if previous_position <= 0.0 or state.entry_price is None:
            state.entry_price = float(execution_price)
        else:
            state.entry_price = (
                (state.entry_price * previous_position) + (float(execution_price) * quantity_delta)
            ) / state.actual_position
    elif state.actual_position <= 0.0:
        state.actual_position = 0.0
        state.entry_price = None

    return fill


def _planned_stop_loss_price(
    *,
    entry_price: float,
    side: OrderSide,
    stop_loss_pct: float | None,
) -> float | None:
    if side != OrderSide.BUY or stop_loss_pct is None:
        return None
    return float(entry_price * (1.0 - (stop_loss_pct / 100.0)))


def _planned_take_profit_price(
    *,
    entry_price: float,
    side: OrderSide,
    take_profit_pct: float | None,
) -> float | None:
    if side != OrderSide.BUY or take_profit_pct is None:
        return None
    return float(entry_price * (1.0 + (take_profit_pct / 100.0)))


def _handle_invalid_open(
    *,
    state: _SequentialRuntimeState,
    gap_policy: GapPolicy,
    bar_index: int,
    timestamp_ms: int,
) -> None:
    state.invalid_open_count += 1
    if gap_policy == GapPolicy.ERROR:
        raise ValueError(
            "Missing valid next-bar open for pending fill(s) "
            f"at index {bar_index} and timestamp {timestamp_ms}"
        )
    if gap_policy == GapPolicy.EXPIRE:
        state.expired_delta_count += _non_zero_pending_count(state.pending)
        state.pending.clear()
        return
    for item in state.pending:
        if item.quantity != 0.0 and not item.deferred:
            item.deferred = True
            state.deferred_delta_count += 1


def _queue_target_delta_from_signal(
    *,
    state: _SequentialRuntimeState,
    strategy: StrategyDefinition,
    bar_model: Any,
    symbol: str,
    timestamp_ms: int,
    signal: int,
) -> None:
    if signal > 0:
        next_raw_target = float(bar_model.target_quantity)
    elif signal < 0:
        next_raw_target = 0.0
    else:
        next_raw_target = state.raw_desired_target

    next_desired_target = _apply_single_target_transforms(
        strategy=strategy,
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        target_quantity=next_raw_target,
    )
    target_delta = next_desired_target - state.desired_target

    state.raw_desired_target = next_raw_target
    state.desired_target = next_desired_target
    if target_delta != 0.0:
        state.pending.append(_PendingDelta(quantity=float(target_delta)))
    if _pending_total(state.pending) == 0.0:
        state.pending.clear()


def _apply_single_target_transforms(
    *,
    strategy: StrategyDefinition,
    symbol: str,
    timestamp_ms: int,
    target_quantity: float,
) -> float:
    execution_targets = ExecutionArrayBundle(
        timestamp_ms=[timestamp_ms],
        target_quantity_by_symbol={symbol: [target_quantity]},
    )
    transformed = _apply_execution_transforms(
        strategy=strategy,
        execution_targets=execution_targets,
    )
    values = _extract_target_values(
        execution_targets=transformed,
        symbol=symbol,
        expected_size=1,
    )
    return float(values[0])


def _build_fill_generation_result(state: _SequentialRuntimeState) -> FillGenerationResult:
    return FillGenerationResult(
        fills=state.fills,
        executed_delta=np.asarray(state.executed_delta, dtype=np.float64),
        executed_notional=np.asarray(state.executed_notional, dtype=np.float64),
        executed_fees=np.asarray(state.executed_fees, dtype=np.float64),
        total_slippage_cost=float(state.total_slippage_cost),
        invalid_open_count=state.invalid_open_count,
        deferred_delta_count=state.deferred_delta_count,
        expired_delta_count=state.expired_delta_count,
        executed_deferred_count=state.executed_deferred_count,
        tail_expired_delta_count=_tail_expired_delta_count(state.pending),
        intrabar_ambiguous_bar_count=state.intrabar_ambiguous_bar_count,
    )


def _is_valid_open(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _apply_slippage(*, raw_open: float, side: OrderSide, slippage_bps: float) -> float:
    factor = slippage_bps / 10_000.0
    if side == OrderSide.BUY:
        return float(raw_open * (1.0 + factor))
    return float(raw_open * (1.0 - factor))


def _stop_loss_fill_price(
    *,
    raw_open: float,
    low_price: float,
    entry_price: float | None,
    stop_loss_pct: float,
    actual_position: float,
) -> float | None:
    if actual_position <= 0.0 or entry_price is None:
        return None

    stop_price = entry_price * (1.0 - (stop_loss_pct / 100.0))
    gap_fill_price = _stop_loss_gap_fill_price(
        raw_open=raw_open,
        stop_price=stop_price,
    )
    if gap_fill_price is not None:
        return gap_fill_price
    if np.isfinite(low_price) and low_price <= stop_price:
        return float(stop_price)
    return None


def _take_profit_fill_price(
    *,
    raw_open: float,
    high_price: float,
    entry_price: float | None,
    take_profit_pct: float,
    actual_position: float,
) -> float | None:
    if actual_position <= 0.0 or entry_price is None:
        return None

    target_price = entry_price * (1.0 + (take_profit_pct / 100.0))
    gap_fill_price = _take_profit_gap_fill_price(
        raw_open=raw_open,
        target_price=target_price,
    )
    if gap_fill_price is not None:
        return gap_fill_price
    if np.isfinite(high_price) and high_price >= target_price:
        return float(target_price)
    return None


@dataclass(frozen=True)
class _ProtectiveExitDecision:
    fill_price: float
    exit_reason: ExitReason
    ambiguous: bool = False


def _protective_exit_fill_price(
    *,
    raw_open: float,
    high_price: float,
    low_price: float,
    entry_price: float | None,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    actual_position: float,
    timestamp_ms: int,
    intrabar_exit_policy: IntrabarExitPolicy,
) -> _ProtectiveExitDecision | None:
    if actual_position <= 0.0 or entry_price is None:
        return None

    stop_price: float | None = None
    target_price: float | None = None

    if stop_loss_pct is not None:
        stop_price = entry_price * (1.0 - (stop_loss_pct / 100.0))
        stop_gap_fill_price = _stop_loss_gap_fill_price(
            raw_open=raw_open,
            stop_price=stop_price,
        )
        if stop_gap_fill_price is not None:
            return _ProtectiveExitDecision(
                fill_price=stop_gap_fill_price,
                exit_reason=ExitReason.STOP_LOSS,
            )

    if take_profit_pct is not None:
        target_price = entry_price * (1.0 + (take_profit_pct / 100.0))
        take_profit_gap_fill_price = _take_profit_gap_fill_price(
            raw_open=raw_open,
            target_price=target_price,
        )
        if take_profit_gap_fill_price is not None:
            return _ProtectiveExitDecision(
                fill_price=take_profit_gap_fill_price,
                exit_reason=ExitReason.TAKE_PROFIT,
            )

    stop_touched = stop_price is not None and np.isfinite(low_price) and low_price <= stop_price
    target_touched = (
        target_price is not None and np.isfinite(high_price) and high_price >= target_price
    )

    if stop_touched and target_touched:
        assert stop_price is not None
        assert target_price is not None
        return _resolve_ambiguous_intrabar_exit(
            stop_price=stop_price,
            target_price=target_price,
            timestamp_ms=timestamp_ms,
            intrabar_exit_policy=intrabar_exit_policy,
        )
    if stop_touched:
        assert stop_price is not None
        return _ProtectiveExitDecision(
            fill_price=float(stop_price),
            exit_reason=ExitReason.STOP_LOSS,
        )
    if target_touched:
        assert target_price is not None
        return _ProtectiveExitDecision(
            fill_price=float(target_price),
            exit_reason=ExitReason.TAKE_PROFIT,
        )

    return None


def _resolve_ambiguous_intrabar_exit(
    *,
    stop_price: float,
    target_price: float,
    timestamp_ms: int,
    intrabar_exit_policy: IntrabarExitPolicy,
) -> _ProtectiveExitDecision:
    if intrabar_exit_policy == IntrabarExitPolicy.ERROR:
        raise ValueError(
            "Ambiguous intrabar protective exit for long position at "
            f"timestamp_ms {timestamp_ms}: both stop_loss and take_profit levels "
            "were touched"
        )
    if intrabar_exit_policy == IntrabarExitPolicy.TAKE_PROFIT_FIRST:
        return _ProtectiveExitDecision(
            fill_price=float(target_price),
            exit_reason=ExitReason.TAKE_PROFIT,
            ambiguous=True,
        )
    return _ProtectiveExitDecision(
        fill_price=float(stop_price),
        exit_reason=ExitReason.STOP_LOSS,
        ambiguous=True,
    )


def _pending_exit_reason_at_open(
    *,
    state: _SequentialRuntimeState,
    pending_total: float,
    raw_open: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
) -> ExitReason | None:
    if pending_total >= 0.0 or state.actual_position <= 0.0 or state.entry_price is None:
        return None

    if stop_loss_pct is not None:
        stop_price = state.entry_price * (1.0 - (stop_loss_pct / 100.0))
        if _stop_loss_gap_fill_price(raw_open=raw_open, stop_price=stop_price) is not None:
            return ExitReason.STOP_LOSS

    if take_profit_pct is not None:
        target_price = state.entry_price * (1.0 + (take_profit_pct / 100.0))
        if _take_profit_gap_fill_price(raw_open=raw_open, target_price=target_price) is not None:
            return ExitReason.TAKE_PROFIT

    return None


def _stop_loss_gap_fill_price(*, raw_open: float, stop_price: float) -> float | None:
    if _is_valid_open(raw_open) and raw_open <= stop_price:
        return raw_open
    return None


def _take_profit_gap_fill_price(*, raw_open: float, target_price: float) -> float | None:
    if _is_valid_open(raw_open) and raw_open >= target_price:
        return raw_open
    return None


def _pending_total(pending: list[_PendingDelta]) -> float:
    return float(sum(item.quantity for item in pending))


def _tail_expired_delta_count(pending: list[_PendingDelta]) -> int:
    return _non_zero_pending_count(pending) if _pending_total(pending) != 0.0 else 0


def _non_zero_pending_count(pending: list[_PendingDelta]) -> int:
    return sum(1 for item in pending if item.quantity != 0.0)


def _format_required_indicator_features(strategy: StrategyDefinition) -> str:
    feature_names = [requirement.feature_name for requirement in strategy.indicator_requirements]
    if not feature_names:
        return "none"
    return ", ".join(feature_names)


def _raise_runtime_invalid_feature_snapshot(
    *,
    strategy: StrategyDefinition,
    symbol: str,
    timestamp_ms: int,
) -> NoReturn:
    required_features = _format_required_indicator_features(strategy)
    raise ValueError(
        "Event-driven bar runtime invalid feature snapshot at "
        f"timestamp_ms {timestamp_ms} for symbol {symbol} "
        f"in strategy '{strategy.strategy_id}'; affected required feature(s): "
        f"{required_features}"
    )


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
        "intrabar_exit_policy": request.execution.intrabar_exit_policy.value,
        "commission_bps": float(request.execution.commission_bps),
        "slippage_bps": float(request.execution.slippage_bps),
        "total_fees": float(fill_result.executed_fees.sum()),
        "total_slippage_cost": float(fill_result.total_slippage_cost),
        "stop_loss_exit_count": _exit_fill_count(
            fills=fill_result.fills,
            exit_reason=ExitReason.STOP_LOSS,
        ),
        "take_profit_exit_count": _exit_fill_count(
            fills=fill_result.fills,
            exit_reason=ExitReason.TAKE_PROFIT,
        ),
        "signal_exit_count": _signal_exit_fill_count(fill_result.fills),
        "intrabar_ambiguous_bar_count": int(fill_result.intrabar_ambiguous_bar_count),
        "invalid_open_count": int(fill_result.invalid_open_count),
        "deferred_delta_count": int(fill_result.deferred_delta_count),
        "expired_delta_count": int(fill_result.expired_delta_count),
        "executed_deferred_count": int(fill_result.executed_deferred_count),
        "tail_expired_delta_count": int(fill_result.tail_expired_delta_count),
    }


def _exit_fill_count(*, fills: list[Fill], exit_reason: ExitReason) -> int:
    return sum(
        1 for fill in fills if fill.side == OrderSide.SELL and fill.exit_reason == exit_reason
    )


def _signal_exit_fill_count(fills: list[Fill]) -> int:
    return sum(
        1
        for fill in fills
        if fill.side == OrderSide.SELL
        and (fill.exit_reason is None or fill.exit_reason == ExitReason.SIGNAL)
    )


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
