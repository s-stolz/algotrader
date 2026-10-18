"""Fill generation for vectorized backtest execution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from domain.enums import ExitReason, GapPolicy, IntrabarExitPolicy, OrderSide
from domain.types import Fill
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class FillGenerationResult:
    fills: list[Fill]
    executed_delta: NDArray[np.float64]
    executed_notional: NDArray[np.float64]
    executed_fees: NDArray[np.float64]
    total_slippage_cost: float
    invalid_open_count: int
    deferred_delta_count: int
    expired_delta_count: int
    executed_deferred_count: int
    tail_expired_delta_count: int
    intrabar_ambiguous_bar_count: int = 0


@dataclass
class _PendingDelta:
    quantity: float
    deferred: bool = False


@dataclass
class _FillState:
    executed_delta: NDArray[np.float64]
    executed_notional: NDArray[np.float64]
    executed_fees: NDArray[np.float64]
    fills: list[Fill]
    total_slippage_cost: float = 0.0
    invalid_open_count: int = 0
    deferred_delta_count: int = 0
    expired_delta_count: int = 0
    executed_deferred_count: int = 0
    intrabar_ambiguous_bar_count: int = 0


@dataclass(frozen=True)
class _ProtectiveExitInputs:
    timestamp_ms: NDArray[np.int64]
    open_prices: NDArray[np.float64]
    high_prices: NDArray[np.float64] | None
    low_prices: NDArray[np.float64] | None
    target_quantity: NDArray[np.float64]
    signal_values: NDArray[np.int64]


@dataclass(frozen=True)
class _ProtectiveExitDecision:
    fill_price: float
    exit_reason: ExitReason
    ambiguous: bool = False


def generate_fills_from_targets(  # noqa: C901
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    target_quantity: ArrayLike,
    gap_policy: GapPolicy = GapPolicy.SKIP,
    slippage_bps: float = 0.0,
    commission_bps: float = 0.0,
) -> FillGenerationResult:
    """Build fills from target quantities using next-bar-open timing.

    Decision at index ``t`` can fill earliest on index ``t+1``.
    Invalid next-open values are NaN, non-finite, or <= 0.
    """

    ts = np.asarray(timestamp_ms, dtype=np.int64)
    opens = np.asarray(open_prices, dtype=np.float64)
    target = np.asarray(target_quantity, dtype=np.float64)
    _validate_fill_inputs(
        ts=ts,
        opens=opens,
        target=target,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )

    if ts.size == 0:
        return _empty_fill_generation_result()

    state = _initialize_fill_state(target)
    pending: list[_PendingDelta] = []
    previous_target = 0.0
    actual_position = 0.0

    for dst_idx in range(1, ts.size):
        src_idx = dst_idx - 1
        next_target = float(target[src_idx])
        if next_target != previous_target:
            effective_position = actual_position + _pending_total(pending)
            decision_delta = next_target - effective_position
            if decision_delta != 0.0:
                pending.append(_PendingDelta(quantity=float(decision_delta)))
            if _pending_total(pending) == 0.0:
                pending.clear()
            previous_target = next_target

        pending_total = _pending_total(pending)
        if pending_total == 0.0:
            pending.clear()
            continue

        raw_open = float(opens[dst_idx])
        if _is_valid_open(raw_open):
            _execute_pending_fill(
                state=state,
                pending=pending,
                symbol=symbol,
                timestamp_ms=int(ts[dst_idx]),
                dst_idx=dst_idx,
                pending_total=pending_total,
                raw_open=raw_open,
                slippage_bps=slippage_bps,
                commission_bps=commission_bps,
            )
            actual_position += pending_total
            continue

        _handle_invalid_open(
            pending=pending,
            state=state,
            gap_policy=gap_policy,
            dst_idx=dst_idx,
            timestamp_ms=int(ts[dst_idx]),
        )

    # Decision on the final bar has no in-range next-open and therefore expires.
    final_target = float(target[-1])
    final_delta = 0.0
    if final_target != previous_target:
        final_delta = final_target - (actual_position + _pending_total(pending))
    if final_delta != 0.0:
        pending.append(_PendingDelta(quantity=float(final_delta)))
        if _pending_total(pending) == 0.0:
            pending.clear()

    return FillGenerationResult(
        fills=state.fills,
        executed_delta=state.executed_delta,
        executed_notional=state.executed_notional,
        executed_fees=state.executed_fees,
        total_slippage_cost=float(state.total_slippage_cost),
        invalid_open_count=state.invalid_open_count,
        deferred_delta_count=state.deferred_delta_count,
        expired_delta_count=state.expired_delta_count,
        executed_deferred_count=state.executed_deferred_count,
        tail_expired_delta_count=_tail_expired_delta_count(pending),
    )


def generate_fills_from_targets_with_stop_loss(
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    target_quantity: ArrayLike,
    signal_values: ArrayLike,
    stop_loss_pct: float,
    high_prices: ArrayLike | None = None,
    low_prices: ArrayLike | None = None,
    gap_policy: GapPolicy = GapPolicy.SKIP,
    slippage_bps: float = 0.0,
    commission_bps: float = 0.0,
) -> FillGenerationResult:
    """Build fills from signal targets and a percent stop loss.

    Long stop checks use ``low_prices``. Short stop checks use ``high_prices``.
    """

    return generate_fills_from_targets_with_protective_exits(
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        open_prices=open_prices,
        high_prices=high_prices,
        low_prices=low_prices,
        target_quantity=target_quantity,
        signal_values=signal_values,
        stop_loss_pct=stop_loss_pct,
        gap_policy=gap_policy,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )


def generate_fills_from_targets_with_protective_exits(
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    target_quantity: ArrayLike,
    signal_values: ArrayLike,
    high_prices: ArrayLike | None = None,
    low_prices: ArrayLike | None = None,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    intrabar_exit_policy: IntrabarExitPolicy = IntrabarExitPolicy.CONSERVATIVE,
    gap_policy: GapPolicy = GapPolicy.SKIP,
    slippage_bps: float = 0.0,
    commission_bps: float = 0.0,
) -> FillGenerationResult:
    """Build fills from signal targets and optional protective exits.

    Signal decisions at index ``t`` fill earliest on index ``t+1``. Once an
    entry fills, protective exits are active for that same destination bar.
    """

    inputs = _prepare_protective_exit_inputs(
        timestamp_ms=timestamp_ms,
        open_prices=open_prices,
        high_prices=high_prices,
        low_prices=low_prices,
        target_quantity=target_quantity,
        signal_values=signal_values,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )
    ts = inputs.timestamp_ms
    opens = inputs.open_prices
    highs = inputs.high_prices
    lows = inputs.low_prices
    target = inputs.target_quantity
    signals = inputs.signal_values

    if ts.size == 0:
        return _empty_fill_generation_result()

    state = _initialize_fill_state(target)
    pending: list[_PendingDelta] = []
    desired_target = 0.0
    actual_position = 0.0
    entry_price: float | None = None

    for dst_idx in range(1, ts.size):
        src_idx = dst_idx - 1
        desired_target = _queue_signal_target_delta(
            pending=pending,
            desired_target=desired_target,
            actual_position=actual_position,
            signal=int(signals[src_idx]),
            signal_target=float(target[src_idx]),
        )

        pending_total = _pending_total(pending)
        if pending_total != 0.0:
            raw_open = float(opens[dst_idx])
            if _is_valid_open(raw_open):
                exit_reason = _pending_exit_reason_at_open(
                    pending_total=pending_total,
                    raw_open=raw_open,
                    entry_price=entry_price,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    actual_position=actual_position,
                )
                fill = _record_fill(
                    state=state,
                    symbol=symbol,
                    timestamp_ms=int(ts[dst_idx]),
                    dst_idx=dst_idx,
                    current_position=actual_position,
                    quantity_delta=pending_total,
                    raw_execution_price=raw_open,
                    slippage_bps=slippage_bps,
                    commission_bps=commission_bps,
                    exit_reason=exit_reason,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                )
                actual_position, entry_price = _apply_position_fill(
                    actual_position=actual_position,
                    entry_price=entry_price,
                    quantity_delta=pending_total,
                    fill_price=float(fill.price),
                )
                state.executed_deferred_count += sum(
                    1 for item in pending if item.deferred and item.quantity != 0.0
                )
                pending.clear()
            else:
                _handle_invalid_open(
                    pending=pending,
                    state=state,
                    gap_policy=gap_policy,
                    dst_idx=dst_idx,
                    timestamp_ms=int(ts[dst_idx]),
                )

        protective_exit = _protective_exit_fill_price(
            raw_open=float(opens[dst_idx]),
            high_price=None if highs is None else float(highs[dst_idx]),
            low_price=None if lows is None else float(lows[dst_idx]),
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            actual_position=actual_position,
            timestamp_ms=int(ts[dst_idx]),
            intrabar_exit_policy=intrabar_exit_policy,
        )
        if protective_exit is not None:
            if protective_exit.ambiguous:
                state.intrabar_ambiguous_bar_count += 1
            fill = _record_fill(
                state=state,
                symbol=symbol,
                timestamp_ms=int(ts[dst_idx]),
                dst_idx=dst_idx,
                current_position=actual_position,
                quantity_delta=-actual_position,
                raw_execution_price=protective_exit.fill_price,
                slippage_bps=slippage_bps,
                commission_bps=commission_bps,
                exit_reason=protective_exit.exit_reason,
            )
            actual_position, entry_price = _apply_position_fill(
                actual_position=actual_position,
                entry_price=entry_price,
                quantity_delta=-actual_position,
                fill_price=float(fill.price),
            )
            desired_target = 0.0
            pending.clear()

    desired_target = _queue_signal_target_delta(
        pending=pending,
        desired_target=desired_target,
        actual_position=actual_position,
        signal=int(signals[-1]),
        signal_target=float(target[-1]),
    )
    _ = desired_target

    return FillGenerationResult(
        fills=state.fills,
        executed_delta=state.executed_delta,
        executed_notional=state.executed_notional,
        executed_fees=state.executed_fees,
        total_slippage_cost=float(state.total_slippage_cost),
        invalid_open_count=state.invalid_open_count,
        deferred_delta_count=state.deferred_delta_count,
        expired_delta_count=state.expired_delta_count,
        executed_deferred_count=state.executed_deferred_count,
        tail_expired_delta_count=_tail_expired_delta_count(pending),
        intrabar_ambiguous_bar_count=state.intrabar_ambiguous_bar_count,
    )


def _is_valid_open(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _apply_slippage(*, raw_open: float, side: OrderSide, slippage_bps: float) -> float:
    factor = slippage_bps / 10_000.0
    if side == OrderSide.BUY:
        return float(raw_open * (1.0 + factor))
    return float(raw_open * (1.0 - factor))


def _validate_fill_inputs(
    *,
    ts: NDArray[np.int64],
    opens: NDArray[np.float64],
    target: NDArray[np.float64],
    slippage_bps: float,
    commission_bps: float,
) -> None:
    if ts.size != opens.size or ts.size != target.size:
        raise ValueError("timestamp, open price, and target arrays must have equal length")
    _validate_cost_input(name="slippage_bps", value=slippage_bps)
    _validate_cost_input(name="commission_bps", value=commission_bps)


def _target_requires_long_stop_prices(target: NDArray[np.float64]) -> bool:
    return bool(np.any(target > 0.0))


def _target_requires_short_stop_prices(target: NDArray[np.float64]) -> bool:
    return bool(np.any(target < 0.0))


def _prepare_protective_exit_inputs(
    *,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    high_prices: ArrayLike | None,
    low_prices: ArrayLike | None,
    target_quantity: ArrayLike,
    signal_values: ArrayLike,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    slippage_bps: float,
    commission_bps: float,
) -> _ProtectiveExitInputs:
    ts = np.asarray(timestamp_ms, dtype=np.int64)
    opens = np.asarray(open_prices, dtype=np.float64)
    highs = None if high_prices is None else np.asarray(high_prices, dtype=np.float64)
    lows = None if low_prices is None else np.asarray(low_prices, dtype=np.float64)
    target = np.asarray(target_quantity, dtype=np.float64)
    signals = np.asarray(signal_values, dtype=np.int64)

    _validate_fill_inputs(
        ts=ts,
        opens=opens,
        target=target,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )
    if ts.size != signals.size:
        raise ValueError("timestamp and signal arrays must have equal length")
    if lows is not None and ts.size != lows.size:
        raise ValueError("timestamp and low price arrays must have equal length")
    if highs is not None and ts.size != highs.size:
        raise ValueError("timestamp and high price arrays must have equal length")
    if stop_loss_pct is not None:
        _validate_stop_loss_pct(stop_loss_pct)
        if _target_requires_long_stop_prices(target) and lows is None:
            raise ValueError(
                "low price array is required when stop_loss_pct is configured for long targets"
            )
        if _target_requires_short_stop_prices(target) and highs is None:
            raise ValueError(
                "high price array is required when stop_loss_pct is configured for short targets"
            )
    if take_profit_pct is not None:
        if highs is None:
            raise ValueError("high price array is required when take_profit_pct is configured")
        _validate_take_profit_pct(take_profit_pct)

    return _ProtectiveExitInputs(
        timestamp_ms=ts,
        open_prices=opens,
        high_prices=highs,
        low_prices=lows,
        target_quantity=target,
        signal_values=signals,
    )


def _validate_cost_input(*, name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} must be >= 0")


def _validate_stop_loss_pct(stop_loss_pct: float) -> None:
    if not np.isfinite(stop_loss_pct) or stop_loss_pct <= 0.0 or stop_loss_pct >= 100.0:
        raise ValueError("stop_loss_pct must be finite and greater than 0 and less than 100")


def _validate_take_profit_pct(take_profit_pct: float) -> None:
    if not np.isfinite(take_profit_pct) or take_profit_pct <= 0.0:
        raise ValueError("take_profit_pct must be finite and greater than 0")


def _empty_fill_generation_result() -> FillGenerationResult:
    empty = np.asarray([], dtype=np.float64)
    return FillGenerationResult(
        fills=[],
        executed_delta=empty,
        executed_notional=empty,
        executed_fees=empty,
        total_slippage_cost=0.0,
        invalid_open_count=0,
        deferred_delta_count=0,
        expired_delta_count=0,
        executed_deferred_count=0,
        tail_expired_delta_count=0,
        intrabar_ambiguous_bar_count=0,
    )


def _initialize_fill_state(target: NDArray[np.float64]) -> _FillState:
    return _FillState(
        executed_delta=np.zeros_like(target, dtype=np.float64),
        executed_notional=np.zeros_like(target, dtype=np.float64),
        executed_fees=np.zeros_like(target, dtype=np.float64),
        fills=[],
    )


def _pending_total(pending: list[_PendingDelta]) -> float:
    return float(sum(item.quantity for item in pending))


def _execute_pending_fill(
    *,
    state: _FillState,
    pending: list[_PendingDelta],
    symbol: str,
    timestamp_ms: int,
    dst_idx: int,
    pending_total: float,
    raw_open: float,
    slippage_bps: float,
    commission_bps: float,
) -> None:
    state.executed_delta[dst_idx] = pending_total
    side = OrderSide.BUY if pending_total > 0 else OrderSide.SELL
    quantity = abs(pending_total)
    execution_price = _apply_slippage(
        raw_open=raw_open,
        side=side,
        slippage_bps=slippage_bps,
    )
    fee = quantity * execution_price * (commission_bps / 10_000.0)

    state.fills.append(
        Fill(
            timestamp_ms=timestamp_ms,
            symbol=symbol,
            quantity=quantity,
            price=execution_price,
            side=side,
            fees=float(fee),
        )
    )
    state.executed_notional[dst_idx] = pending_total * execution_price
    state.executed_fees[dst_idx] = float(fee)
    state.total_slippage_cost += quantity * abs(execution_price - raw_open)
    state.executed_deferred_count += sum(
        1 for item in pending if item.deferred and item.quantity != 0.0
    )
    pending.clear()


def _queue_signal_target_delta(
    *,
    pending: list[_PendingDelta],
    desired_target: float,
    actual_position: float,
    signal: int,
    signal_target: float,
) -> float:
    if signal == 0:
        return desired_target

    next_desired_target = signal_target
    if next_desired_target == desired_target:
        return desired_target

    effective_position = actual_position + _pending_total(pending)
    target_delta = next_desired_target - effective_position
    if target_delta != 0.0:
        pending.append(_PendingDelta(quantity=float(target_delta)))
    if _pending_total(pending) == 0.0:
        pending.clear()
    return next_desired_target


def _record_fill(
    *,
    state: _FillState,
    symbol: str,
    timestamp_ms: int,
    dst_idx: int,
    current_position: float,
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
    opening_side = _opening_side_for_fill(
        current_position=current_position,
        quantity_delta=quantity_delta,
    )
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
            opening_side=opening_side,
            stop_loss_pct=stop_loss_pct,
        ),
        take_profit_price=_planned_take_profit_price(
            entry_price=execution_price,
            opening_side=opening_side,
            take_profit_pct=take_profit_pct,
        ),
    )

    state.fills.append(fill)
    state.executed_delta[dst_idx] += quantity_delta
    state.executed_notional[dst_idx] += quantity_delta * execution_price
    state.executed_fees[dst_idx] += float(fee)
    state.total_slippage_cost += quantity * abs(execution_price - raw_execution_price)
    return fill


def _opening_side_for_fill(
    *,
    current_position: float,
    quantity_delta: float,
) -> OrderSide | None:
    next_position = current_position + quantity_delta
    if quantity_delta > 0.0 and next_position > 0.0:
        return OrderSide.BUY
    if quantity_delta < 0.0 and next_position < 0.0:
        return OrderSide.SELL
    return None


def _planned_stop_loss_price(
    *,
    entry_price: float,
    opening_side: OrderSide | None,
    stop_loss_pct: float | None,
) -> float | None:
    if opening_side is None or stop_loss_pct is None:
        return None
    if opening_side == OrderSide.BUY:
        return float(entry_price * (1.0 - (stop_loss_pct / 100.0)))
    return float(entry_price * (1.0 + (stop_loss_pct / 100.0)))


def _planned_take_profit_price(
    *,
    entry_price: float,
    opening_side: OrderSide | None,
    take_profit_pct: float | None,
) -> float | None:
    if opening_side is None or take_profit_pct is None:
        return None
    if opening_side == OrderSide.BUY:
        return float(entry_price * (1.0 + (take_profit_pct / 100.0)))
    return float(entry_price * (1.0 - (take_profit_pct / 100.0)))


def _apply_position_fill(
    *,
    actual_position: float,
    entry_price: float | None,
    quantity_delta: float,
    fill_price: float,
) -> tuple[float, float | None]:
    if quantity_delta == 0.0:
        return actual_position, entry_price

    next_position = actual_position + quantity_delta
    if actual_position == 0.0 or _same_direction(actual_position, quantity_delta):
        previous_abs_position = abs(actual_position)
        added_abs_quantity = abs(quantity_delta)
        if previous_abs_position == 0.0 or entry_price is None:
            return next_position, fill_price
        new_entry_price = (
            (entry_price * previous_abs_position) + (fill_price * added_abs_quantity)
        ) / (previous_abs_position + added_abs_quantity)
        return next_position, new_entry_price
    if next_position == 0.0:
        return 0.0, None
    if _same_direction(actual_position, next_position):
        return next_position, entry_price
    return next_position, fill_price


def _same_direction(left: float, right: float) -> bool:
    return (left > 0.0 and right > 0.0) or (left < 0.0 and right < 0.0)


def _stop_loss_fill_price(
    *,
    raw_open: float,
    low_price: float | None,
    entry_price: float | None,
    stop_loss_pct: float,
    actual_position: float,
) -> float | None:
    if actual_position == 0.0 or entry_price is None:
        return None

    stop_price = _stop_loss_price(
        entry_price=entry_price,
        stop_loss_pct=stop_loss_pct,
        actual_position=actual_position,
    )
    gap_fill_price = _stop_loss_gap_fill_price(
        raw_open=raw_open,
        stop_price=stop_price,
        actual_position=actual_position,
    )
    if gap_fill_price is not None:
        return gap_fill_price
    if _stop_loss_touched(
        high_price=None,
        low_price=low_price,
        stop_price=stop_price,
        actual_position=actual_position,
    ):
        return float(stop_price)
    return None


def _take_profit_fill_price(
    *,
    raw_open: float,
    high_price: float | None,
    entry_price: float | None,
    take_profit_pct: float,
    actual_position: float,
) -> float | None:
    if actual_position == 0.0 or entry_price is None:
        return None

    target_price = _take_profit_price(
        entry_price=entry_price,
        take_profit_pct=take_profit_pct,
        actual_position=actual_position,
    )
    gap_fill_price = _take_profit_gap_fill_price(
        raw_open=raw_open,
        target_price=target_price,
        actual_position=actual_position,
    )
    if gap_fill_price is not None:
        return gap_fill_price
    if _take_profit_touched(
        high_price=high_price,
        low_price=None,
        target_price=target_price,
        actual_position=actual_position,
    ):
        return float(target_price)
    return None


def _protective_exit_fill_price(
    *,
    raw_open: float,
    high_price: float | None,
    low_price: float | None,
    entry_price: float | None,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    actual_position: float,
    timestamp_ms: int,
    intrabar_exit_policy: IntrabarExitPolicy,
) -> _ProtectiveExitDecision | None:
    if actual_position == 0.0 or entry_price is None:
        return None

    stop_price: float | None = None
    target_price: float | None = None

    if stop_loss_pct is not None:
        stop_price = _stop_loss_price(
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            actual_position=actual_position,
        )
        stop_gap_fill_price = _stop_loss_gap_fill_price(
            raw_open=raw_open,
            stop_price=stop_price,
            actual_position=actual_position,
        )
        if stop_gap_fill_price is not None:
            return _ProtectiveExitDecision(
                fill_price=stop_gap_fill_price,
                exit_reason=ExitReason.STOP_LOSS,
            )

    if take_profit_pct is not None:
        target_price = _take_profit_price(
            entry_price=entry_price,
            take_profit_pct=take_profit_pct,
            actual_position=actual_position,
        )
        take_profit_gap_fill_price = _take_profit_gap_fill_price(
            raw_open=raw_open,
            target_price=target_price,
            actual_position=actual_position,
        )
        if take_profit_gap_fill_price is not None:
            return _ProtectiveExitDecision(
                fill_price=take_profit_gap_fill_price,
                exit_reason=ExitReason.TAKE_PROFIT,
            )

    stop_touched = _stop_loss_touched(
        high_price=high_price,
        low_price=low_price,
        stop_price=stop_price,
        actual_position=actual_position,
    )
    target_touched = _take_profit_touched(
        high_price=high_price,
        low_price=low_price,
        target_price=target_price,
        actual_position=actual_position,
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
            "Ambiguous intrabar protective exit at "
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
    pending_total: float,
    raw_open: float,
    entry_price: float | None,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    actual_position: float,
) -> ExitReason | None:
    if not _same_direction(actual_position, -pending_total) or entry_price is None:
        return None

    if stop_loss_pct is not None:
        stop_price = _stop_loss_price(
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            actual_position=actual_position,
        )
        if (
            _stop_loss_gap_fill_price(
                raw_open=raw_open,
                stop_price=stop_price,
                actual_position=actual_position,
            )
            is not None
        ):
            return ExitReason.STOP_LOSS

    if take_profit_pct is not None:
        target_price = _take_profit_price(
            entry_price=entry_price,
            take_profit_pct=take_profit_pct,
            actual_position=actual_position,
        )
        if (
            _take_profit_gap_fill_price(
                raw_open=raw_open,
                target_price=target_price,
                actual_position=actual_position,
            )
            is not None
        ):
            return ExitReason.TAKE_PROFIT

    return None


def _stop_loss_price(
    *,
    entry_price: float,
    stop_loss_pct: float,
    actual_position: float,
) -> float:
    if actual_position > 0.0:
        return float(entry_price * (1.0 - (stop_loss_pct / 100.0)))
    return float(entry_price * (1.0 + (stop_loss_pct / 100.0)))


def _take_profit_price(
    *,
    entry_price: float,
    take_profit_pct: float,
    actual_position: float,
) -> float:
    if actual_position > 0.0:
        return float(entry_price * (1.0 + (take_profit_pct / 100.0)))
    return float(entry_price * (1.0 - (take_profit_pct / 100.0)))


def _stop_loss_gap_fill_price(
    *,
    raw_open: float,
    stop_price: float,
    actual_position: float,
) -> float | None:
    if actual_position > 0.0 and _is_valid_open(raw_open) and raw_open <= stop_price:
        return raw_open
    if actual_position < 0.0 and _is_valid_open(raw_open) and raw_open >= stop_price:
        return raw_open
    return None


def _take_profit_gap_fill_price(
    *,
    raw_open: float,
    target_price: float,
    actual_position: float,
) -> float | None:
    if actual_position > 0.0 and _is_valid_open(raw_open) and raw_open >= target_price:
        return raw_open
    if actual_position < 0.0 and _is_valid_open(raw_open) and raw_open <= target_price:
        return raw_open
    return None


def _stop_loss_touched(
    *,
    high_price: float | None,
    low_price: float | None,
    stop_price: float | None,
    actual_position: float,
) -> bool:
    if stop_price is None:
        return False
    if actual_position > 0.0:
        return bool(low_price is not None and np.isfinite(low_price) and low_price <= stop_price)
    return bool(high_price is not None and np.isfinite(high_price) and high_price >= stop_price)


def _take_profit_touched(
    *,
    high_price: float | None,
    low_price: float | None,
    target_price: float | None,
    actual_position: float,
) -> bool:
    if target_price is None:
        return False
    if actual_position > 0.0:
        return bool(
            high_price is not None and np.isfinite(high_price) and high_price >= target_price
        )
    return bool(low_price is not None and np.isfinite(low_price) and low_price <= target_price)


def _handle_invalid_open(
    *,
    pending: list[_PendingDelta],
    state: _FillState,
    gap_policy: GapPolicy,
    dst_idx: int,
    timestamp_ms: int,
) -> None:
    state.invalid_open_count += 1
    if gap_policy == GapPolicy.ERROR:
        raise ValueError(
            "Missing valid next-bar open for pending fill(s) "
            f"at index {dst_idx} and timestamp {timestamp_ms}"
        )
    if gap_policy == GapPolicy.EXPIRE:
        state.expired_delta_count += _non_zero_pending_count(pending)
        pending.clear()
        return
    for item in pending:
        if item.quantity != 0.0 and not item.deferred:
            item.deferred = True
            state.deferred_delta_count += 1


def _tail_expired_delta_count(pending: list[_PendingDelta]) -> int:
    return _non_zero_pending_count(pending) if _pending_total(pending) != 0.0 else 0


def _non_zero_pending_count(pending: list[_PendingDelta]) -> int:
    return sum(1 for item in pending if item.quantity != 0.0)
