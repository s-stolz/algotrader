"""Portfolio and equity-curve accounting helpers."""

from __future__ import annotations

import numpy as np
from domain.types import PortfolioSnapshot
from numpy.typing import ArrayLike


def build_equity_curve(
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    close_prices: ArrayLike,
    executed_delta: ArrayLike,
    executed_notional: ArrayLike,
    executed_fees: ArrayLike,
    initial_capital: float,
) -> list[PortfolioSnapshot]:
    """Build account snapshots from execution and close-based mark-to-market.

    Fills update cash from next-open execution notional + fees.
    Unrealized PnL and equity are marked on each bar close.
    """

    ts = np.asarray(timestamp_ms, dtype=np.int64)
    closes = np.asarray(close_prices, dtype=np.float64)
    delta = np.asarray(executed_delta, dtype=np.float64)
    notional = np.asarray(executed_notional, dtype=np.float64)
    fees = np.asarray(executed_fees, dtype=np.float64)

    if (
        ts.size != closes.size
        or ts.size != delta.size
        or ts.size != notional.size
        or ts.size != fees.size
    ):
        raise ValueError(
            "timestamp, close price, delta, execution notional, "
            "and fee arrays must have equal length"
        )

    if ts.size == 0:
        return []

    cash = float(initial_capital) + np.cumsum(-notional - fees)
    position = np.cumsum(delta)
    equity = cash + position * closes

    snapshots: list[PortfolioSnapshot] = []
    for idx in range(ts.size):
        qty = float(position[idx])
        snapshots.append(
            PortfolioSnapshot(
                timestamp_ms=int(ts[idx]),
                cash=float(cash[idx]),
                equity=float(equity[idx]),
                positions={symbol: qty} if qty != 0.0 else {},
            )
        )

    return snapshots
