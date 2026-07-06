"""Trade lifecycle construction from fills."""

from __future__ import annotations

from typing import List, Sequence

from domain.enums import ExitReason, OrderSide, TradeDirection
from domain.types import Fill, Trade


def build_trades_from_fills(fills: Sequence[Fill]) -> List[Trade]:
    """Create closed trades from chronological fills.

    Average-cost accounting supports one signed position per symbol stream.
    """

    trades: List[Trade] = []

    open_qty = 0.0
    avg_entry_price = 0.0
    open_entry_fees = 0.0
    entry_timestamp_ms = 0
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    trade_counter = 0

    for fill in fills:
        qty = float(fill.quantity)
        if qty <= 0.0:
            continue

        fill_fees = max(0.0, float(fill.fees))
        signed_delta = qty if fill.side == OrderSide.BUY else -qty

        if open_qty == 0.0 or _same_direction(open_qty, signed_delta):
            previous_abs_qty = abs(open_qty)
            added_abs_qty = abs(signed_delta)
            new_abs_qty = previous_abs_qty + added_abs_qty
            if previous_abs_qty == 0.0:
                entry_timestamp_ms = int(fill.timestamp_ms)
                avg_entry_price = float(fill.price)
            else:
                avg_entry_price = (
                    (avg_entry_price * previous_abs_qty) + (float(fill.price) * added_abs_qty)
                ) / new_abs_qty
            stop_loss_price = _weighted_optional_price(
                current_value=stop_loss_price,
                current_qty=previous_abs_qty,
                added_value=_optional_float(fill.stop_loss_price),
                added_qty=added_abs_qty,
            )
            take_profit_price = _weighted_optional_price(
                current_value=take_profit_price,
                current_qty=previous_abs_qty,
                added_value=_optional_float(fill.take_profit_price),
                added_qty=added_abs_qty,
            )
            open_qty += signed_delta
            open_entry_fees += fill_fees
            continue

        previous_open_qty = open_qty
        previous_abs_qty = abs(previous_open_qty)
        close_qty = min(previous_abs_qty, qty)
        entry_fee_share = (
            0.0 if previous_abs_qty == 0.0 else open_entry_fees * (close_qty / previous_abs_qty)
        )
        exit_fee_share = 0.0 if qty == 0.0 else fill_fees * (close_qty / qty)
        trade_fees = max(0.0, entry_fee_share + exit_fee_share)
        trade_direction = _trade_direction_for_open_qty(previous_open_qty)
        if trade_direction == TradeDirection.LONG:
            gross_pnl = (float(fill.price) - avg_entry_price) * close_qty
        else:
            gross_pnl = (avg_entry_price - float(fill.price)) * close_qty
        realized_pnl = gross_pnl - trade_fees
        trade_counter += 1
        trades.append(
            Trade(
                trade_id=f"{fill.symbol}-trade-{trade_counter}",
                symbol=fill.symbol,
                trade_direction=trade_direction,
                quantity=close_qty,
                entry_timestamp_ms=entry_timestamp_ms,
                entry_price=avg_entry_price,
                exit_timestamp_ms=int(fill.timestamp_ms),
                exit_price=float(fill.price),
                realized_pnl=realized_pnl,
                fees=trade_fees,
                exit_reason=_exit_reason_from_fill(fill),
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
            )
        )

        remaining_open_abs_qty = previous_abs_qty - close_qty
        remaining_fill_abs_qty = qty - close_qty
        if remaining_open_abs_qty > 0.0:
            open_qty = _signed_quantity(
                abs_quantity=remaining_open_abs_qty,
                direction=trade_direction,
            )
            open_entry_fees = max(0.0, open_entry_fees - entry_fee_share)
            continue

        avg_entry_price = 0.0
        open_entry_fees = 0.0
        open_qty = 0.0
        entry_timestamp_ms = 0
        stop_loss_price = None
        take_profit_price = None

        if remaining_fill_abs_qty > 0.0:
            open_qty = _signed_delta_for_side(
                side=fill.side,
                quantity=remaining_fill_abs_qty,
            )
            entry_timestamp_ms = int(fill.timestamp_ms)
            avg_entry_price = float(fill.price)
            open_entry_fees = max(0.0, fill_fees - exit_fee_share)
            stop_loss_price = _optional_float(fill.stop_loss_price)
            take_profit_price = _optional_float(fill.take_profit_price)

    return trades


def _same_direction(current_qty: float, signed_delta: float) -> bool:
    return (current_qty > 0.0 and signed_delta > 0.0) or (
        current_qty < 0.0 and signed_delta < 0.0
    )


def _trade_direction_for_open_qty(open_qty: float) -> TradeDirection:
    if open_qty > 0.0:
        return TradeDirection.LONG
    if open_qty < 0.0:
        return TradeDirection.SHORT
    raise ValueError("Cannot determine trade direction for a flat position")


def _signed_quantity(*, abs_quantity: float, direction: TradeDirection) -> float:
    if direction == TradeDirection.LONG:
        return abs_quantity
    return -abs_quantity


def _signed_delta_for_side(*, side: OrderSide, quantity: float) -> float:
    if side == OrderSide.BUY:
        return quantity
    return -quantity


def _exit_reason_from_fill(fill: Fill) -> ExitReason:
    if fill.exit_reason is None:
        return ExitReason.SIGNAL
    return ExitReason(fill.exit_reason)


def _optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _weighted_optional_price(
    *,
    current_value: float | None,
    current_qty: float,
    added_value: float | None,
    added_qty: float,
) -> float | None:
    if current_value is None and added_value is None:
        return None
    if current_value is None:
        return added_value
    if added_value is None:
        return current_value
    total_qty = current_qty + added_qty
    if total_qty <= 0.0:
        return None
    return ((current_value * current_qty) + (added_value * added_qty)) / total_qty
