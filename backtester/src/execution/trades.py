"""Trade lifecycle construction from fills."""

from __future__ import annotations

from typing import List, Sequence

from domain.enums import OrderSide
from domain.types import Fill, Trade


def build_trades_from_fills(fills: Sequence[Fill]) -> List[Trade]:
    """Create closed trades from chronological fills.

    Baseline policy is long-only average-cost accounting.
    """

    trades: List[Trade] = []

    open_qty = 0.0
    avg_entry_price = 0.0
    entry_timestamp_ms = 0
    trade_counter = 0

    for fill in fills:
        qty = float(fill.quantity)
        if qty <= 0.0:
            continue

        if fill.side == OrderSide.BUY:
            if open_qty == 0.0:
                entry_timestamp_ms = int(fill.timestamp_ms)
                avg_entry_price = float(fill.price)
                open_qty = qty
                continue

            new_qty = open_qty + qty
            avg_entry_price = ((avg_entry_price * open_qty) + (float(fill.price) * qty)) / new_qty
            open_qty = new_qty
            continue

        if fill.side == OrderSide.SELL and open_qty > 0.0:
            close_qty = min(open_qty, qty)
            realized_pnl = (float(fill.price) - avg_entry_price) * close_qty
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
                )
            )
            open_qty -= close_qty
            if open_qty == 0.0:
                avg_entry_price = 0.0
                entry_timestamp_ms = 0

    return trades
