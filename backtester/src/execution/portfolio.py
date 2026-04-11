"""Portfolio and equity-curve accounting helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
from domain.types import PortfolioSnapshot
from numpy.typing import ArrayLike


def build_equity_curve(
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    executed_delta: ArrayLike,
    initial_capital: float,
) -> list[PortfolioSnapshot]:
    """Build account snapshots from executed fill deltas.

    `executed_delta[i]` is the quantity change executed at timestamp `i`.
    """

    ts = np.asarray(timestamp_ms, dtype=np.int64)
    opens = np.asarray(open_prices, dtype=np.float64)
    delta = np.asarray(executed_delta, dtype=np.float64)

    if ts.size != opens.size or ts.size != delta.size:
        raise ValueError("timestamp, open price, and delta arrays must have equal length")

    if ts.size == 0:
        return []

    cash = float(initial_capital) + np.cumsum(-delta * np.nan_to_num(opens, nan=0.0))
    position = np.cumsum(delta)

    # Use forward-filled prices for mark-to-market valuation on missing open values.
    valuation_price = pd.Series(opens).ffill().fillna(0.0).to_numpy(dtype=np.float64)
    equity = cash + position * valuation_price

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
