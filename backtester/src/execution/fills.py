"""Fill generation for vectorized backtest execution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from domain.enums import ExitReason, GapPolicy, OrderSide
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


def generate_fills_from_targets(
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

    previous_target = np.concatenate(([0.0], target[:-1]))
    target_delta = target - previous_target
    state = _initialize_fill_state(target)
    pending: list[_PendingDelta] = []

    for dst_idx in range(1, ts.size):
        src_idx = dst_idx - 1
        decision_delta = float(target_delta[src_idx])
        if decision_delta != 0.0:
            pending.append(_PendingDelta(quantity=decision_delta))

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
            continue

        _handle_invalid_open(
            pending=pending,
            state=state,
            gap_policy=gap_policy,
            dst_idx=dst_idx,
            timestamp_ms=int(ts[dst_idx]),
        )

    # Decision on the final bar has no in-range next-open and therefore expires.
    final_delta = float(target_delta[-1])
    if final_delta != 0.0:
        pending.append(_PendingDelta(quantity=final_delta))

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
    low_prices: ArrayLike,
    target_quantity: ArrayLike,
    signal_values: ArrayLike,
    stop_loss_pct: float,
    gap_policy: GapPolicy = GapPolicy.SKIP,
    slippage_bps: float = 0.0,
    commission_bps: float = 0.0,
) -> FillGenerationResult:
    """Build fills from signal targets and a percent stop loss.

    Signal decisions at index ``t`` fill earliest on index ``t+1``. Once a long
    entry fills, the stop is active for that same destination bar.
    """

    ts = np.asarray(timestamp_ms, dtype=np.int64)
    opens = np.asarray(open_prices, dtype=np.float64)
    lows = np.asarray(low_prices, dtype=np.float64)
    target = np.asarray(target_quantity, dtype=np.float64)
    signals = np.asarray(signal_values, dtype=np.int64)
    _validate_fill_inputs(
        ts=ts,
        opens=opens,
        target=target,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )
    if ts.size != lows.size or ts.size != signals.size:
        raise ValueError("timestamp, low price, and signal arrays must have equal length")
    _validate_stop_loss_pct(stop_loss_pct)

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
                    actual_position=actual_position,
                )
                fill = _record_fill(
                    state=state,
                    symbol=symbol,
                    timestamp_ms=int(ts[dst_idx]),
                    dst_idx=dst_idx,
                    quantity_delta=pending_total,
                    raw_execution_price=raw_open,
                    slippage_bps=slippage_bps,
                    commission_bps=commission_bps,
                    exit_reason=exit_reason,
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

        stop_fill_price = _stop_loss_fill_price(
            raw_open=float(opens[dst_idx]),
            low_price=float(lows[dst_idx]),
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            actual_position=actual_position,
        )
        if stop_fill_price is not None:
            fill = _record_fill(
                state=state,
                symbol=symbol,
                timestamp_ms=int(ts[dst_idx]),
                dst_idx=dst_idx,
                quantity_delta=-actual_position,
                raw_execution_price=stop_fill_price,
                slippage_bps=slippage_bps,
                commission_bps=commission_bps,
                exit_reason=ExitReason.STOP_LOSS,
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


def _validate_cost_input(*, name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} must be >= 0")


def _validate_stop_loss_pct(stop_loss_pct: float) -> None:
    if not np.isfinite(stop_loss_pct) or stop_loss_pct <= 0.0 or stop_loss_pct >= 100.0:
        raise ValueError("stop_loss_pct must be finite and greater than 0 and less than 100")


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
    signal: int,
    signal_target: float,
) -> float:
    if signal == 0:
        return desired_target

    next_desired_target = signal_target
    target_delta = next_desired_target - desired_target
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
    quantity_delta: float,
    raw_execution_price: float,
    slippage_bps: float,
    commission_bps: float,
    exit_reason: ExitReason | None,
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
    )

    state.fills.append(fill)
    state.executed_delta[dst_idx] += quantity_delta
    state.executed_notional[dst_idx] += quantity_delta * execution_price
    state.executed_fees[dst_idx] += float(fee)
    state.total_slippage_cost += quantity * abs(execution_price - raw_execution_price)
    return fill


def _apply_position_fill(
    *,
    actual_position: float,
    entry_price: float | None,
    quantity_delta: float,
    fill_price: float,
) -> tuple[float, float | None]:
    if quantity_delta > 0.0:
        if actual_position <= 0.0 or entry_price is None:
            return actual_position + quantity_delta, fill_price
        new_position = actual_position + quantity_delta
        new_entry_price = ((entry_price * actual_position) + (fill_price * quantity_delta)) / (
            new_position
        )
        return new_position, new_entry_price

    next_position = actual_position + quantity_delta
    if next_position <= 0.0:
        return 0.0, None
    return next_position, entry_price


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


def _pending_exit_reason_at_open(
    *,
    pending_total: float,
    raw_open: float,
    entry_price: float | None,
    stop_loss_pct: float,
    actual_position: float,
) -> ExitReason | None:
    if pending_total >= 0.0 or actual_position <= 0.0 or entry_price is None:
        return None

    stop_price = entry_price * (1.0 - (stop_loss_pct / 100.0))
    if _stop_loss_gap_fill_price(raw_open=raw_open, stop_price=stop_price) is None:
        return None
    return ExitReason.STOP_LOSS


def _stop_loss_gap_fill_price(*, raw_open: float, stop_price: float) -> float | None:
    if _is_valid_open(raw_open) and raw_open <= stop_price:
        return raw_open
    return None


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
