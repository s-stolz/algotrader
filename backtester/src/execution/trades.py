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
                continue

            new_qty = open_qty + qty
            avg_entry_price = ((avg_entry_price * open_qty) + (float(fill.price) * qty)) / new_qty
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
                )
            )
            open_qty -= close_qty
            open_entry_fees = max(0.0, open_entry_fees - entry_fee_share)
            if open_qty == 0.0:
                avg_entry_price = 0.0
                open_entry_fees = 0.0
                entry_timestamp_ms = 0

    return trades


def _exit_reason_from_fill(fill: Fill) -> ExitReason:
    if fill.exit_reason is None:
        return ExitReason.SIGNAL
    return ExitReason(fill.exit_reason)
