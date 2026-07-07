"""Trade lifecycle construction from fills."""

from __future__ import annotations

from typing import List, Sequence

from domain.enums import ExitReason, OrderSide, TradeDirection
from domain.types import Fill, Trade


def build_trades_from_fills(fills: Sequence[Fill]) -> List[Trade]:
    """Create closed trades from chronological fills."""

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
        fill_price = float(fill.price)
        signed_fill_qty = _signed_fill_quantity(fill.side, qty)

        if _is_flat(open_qty):
            entry_timestamp_ms = int(fill.timestamp_ms)
            avg_entry_price = fill_price
            open_qty = signed_fill_qty
            open_entry_fees = fill_fees
            stop_loss_price = _optional_float(fill.stop_loss_price)
            take_profit_price = _optional_float(fill.take_profit_price)
            continue

        if _same_direction(open_qty, signed_fill_qty):
            open_abs_qty = abs(open_qty)
            new_abs_qty = open_abs_qty + qty
            avg_entry_price = ((avg_entry_price * open_abs_qty) + (fill_price * qty)) / new_abs_qty
            stop_loss_price = _weighted_optional_price(
                current_value=stop_loss_price,
                current_qty=open_abs_qty,
                added_value=_optional_float(fill.stop_loss_price),
                added_qty=qty,
            )
            take_profit_price = _weighted_optional_price(
                current_value=take_profit_price,
                current_qty=open_abs_qty,
                added_value=_optional_float(fill.take_profit_price),
                added_qty=qty,
            )
            open_qty += signed_fill_qty
            open_entry_fees += fill_fees
            continue

        open_abs_qty = abs(open_qty)
        close_qty = min(open_abs_qty, qty)
        opening_qty = qty - close_qty
        trade_direction = TradeDirection.LONG if open_qty > 0.0 else TradeDirection.SHORT
        gross_pnl = _gross_pnl(
            trade_direction=trade_direction,
            entry_price=avg_entry_price,
            exit_price=fill_price,
            quantity=close_qty,
        )
        entry_fee_share = open_entry_fees * (close_qty / open_abs_qty)
        exit_fee_share = fill_fees * (close_qty / qty)
        trade_fees = max(0.0, entry_fee_share + exit_fee_share)
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
                exit_price=fill_price,
                realized_pnl=realized_pnl,
                fees=trade_fees,
                exit_reason=_exit_reason_from_fill(fill),
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
            )
        )

        remaining_open_abs_qty = open_abs_qty - close_qty
        if not _is_flat(remaining_open_abs_qty):
            open_qty = remaining_open_abs_qty if open_qty > 0.0 else -remaining_open_abs_qty
            open_entry_fees = max(0.0, open_entry_fees - entry_fee_share)
            continue

        open_qty = 0.0
        avg_entry_price = 0.0
        open_entry_fees = 0.0
        entry_timestamp_ms = 0
        stop_loss_price = None
        take_profit_price = None

        if not _is_flat(opening_qty):
            entry_timestamp_ms = int(fill.timestamp_ms)
            avg_entry_price = fill_price
            open_qty = _signed_fill_quantity(fill.side, opening_qty)
            open_entry_fees = fill_fees * (opening_qty / qty)
            stop_loss_price = _optional_float(fill.stop_loss_price)
            take_profit_price = _optional_float(fill.take_profit_price)

    return trades


def _signed_fill_quantity(side: OrderSide, quantity: float) -> float:
    if side == OrderSide.BUY:
        return quantity
    return -quantity


def _same_direction(left_qty: float, right_qty: float) -> bool:
    return (left_qty > 0.0 and right_qty > 0.0) or (left_qty < 0.0 and right_qty < 0.0)


def _is_flat(quantity: float) -> bool:
    return abs(quantity) <= 1e-12


def _gross_pnl(
    *,
    trade_direction: TradeDirection,
    entry_price: float,
    exit_price: float,
    quantity: float,
) -> float:
    if trade_direction == TradeDirection.LONG:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity


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
