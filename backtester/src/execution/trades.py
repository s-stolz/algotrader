"""Trade lifecycle construction from fills."""

from __future__ import annotations

from typing import List, Sequence

from domain.enums import ExitReason, OrderSide
from domain.types import Fill, Trade


def build_trades_from_fills(fills: Sequence[Fill]) -> List[Trade]:
    """Create closed trades from chronological fills.

    Baseline policy is long-only average-cost accounting.
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

        if fill.side == OrderSide.BUY:
            if open_qty == 0.0:
                entry_timestamp_ms = int(fill.timestamp_ms)
                avg_entry_price = float(fill.price)
                open_qty = qty
                open_entry_fees = fill_fees
                stop_loss_price = _optional_float(fill.stop_loss_price)
                take_profit_price = _optional_float(fill.take_profit_price)
                continue

            new_qty = open_qty + qty
            avg_entry_price = ((avg_entry_price * open_qty) + (float(fill.price) * qty)) / new_qty
            stop_loss_price = _weighted_optional_price(
                current_value=stop_loss_price,
                current_qty=open_qty,
                added_value=_optional_float(fill.stop_loss_price),
                added_qty=qty,
            )
            take_profit_price = _weighted_optional_price(
                current_value=take_profit_price,
                current_qty=open_qty,
                added_value=_optional_float(fill.take_profit_price),
                added_qty=qty,
            )
            open_qty = new_qty
            open_entry_fees += fill_fees
            continue

        if fill.side == OrderSide.SELL and open_qty <= 0.0:
            raise ValueError(
                "Encountered SELL fill without an open long position; "
                "short accounting is not supported in this baseline"
            )

        if fill.side == OrderSide.SELL and open_qty > 0.0:
            close_qty = min(open_qty, qty)
            gross_pnl = (float(fill.price) - avg_entry_price) * close_qty
            entry_fee_share = 0.0 if open_qty == 0.0 else open_entry_fees * (close_qty / open_qty)
            exit_fee_share = 0.0 if qty == 0.0 else fill_fees * (close_qty / qty)
            trade_fees = max(0.0, entry_fee_share + exit_fee_share)
            realized_pnl = gross_pnl - trade_fees
            trade_counter += 1
            trades.append(
                Trade(
                    trade_id=f"{fill.symbol}-trade-{trade_counter}",
                    symbol=fill.symbol,
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
            open_qty -= close_qty
            open_entry_fees = max(0.0, open_entry_fees - entry_fee_share)
            if open_qty == 0.0:
                avg_entry_price = 0.0
                open_entry_fees = 0.0
                entry_timestamp_ms = 0
                stop_loss_price = None
                take_profit_price = None

    return trades


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
