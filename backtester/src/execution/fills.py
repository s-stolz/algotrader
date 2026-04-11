"""Fill generation for vectorized backtest execution."""

from __future__ import annotations

import numpy as np
from domain.enums import GapPolicy, OrderSide
from domain.types import Fill
from numpy.typing import ArrayLike, NDArray


def generate_fills_from_targets(
    *,
    symbol: str,
    timestamp_ms: ArrayLike,
    open_prices: ArrayLike,
    target_quantity: ArrayLike,
    gap_policy: GapPolicy = GapPolicy.SKIP,
) -> tuple[list[Fill], NDArray[np.float64]]:
    """Build fills from target quantities using next-bar-open timing.

    Decision at index ``t`` can fill earliest on index ``t+1``.
    Returns both the fill objects and the executed quantity delta per bar index.
    """

    ts = np.asarray(timestamp_ms, dtype=np.int64)
    opens = np.asarray(open_prices, dtype=np.float64)
    target = np.asarray(target_quantity, dtype=np.float64)

    if ts.size != opens.size or ts.size != target.size:
        raise ValueError("timestamp, open price, and target arrays must have equal length")

    if ts.size == 0:
        return [], np.asarray([], dtype=np.float64)

    previous_target = np.concatenate(([0.0], target[:-1]))
    target_delta = target - previous_target

    # Decision at t fills at t+1, therefore last delta cannot be filled in-bar mode.
    executable_idx = np.nonzero(target_delta[:-1])[0]
    fill_idx = executable_idx + 1

    executed_delta = np.zeros_like(target, dtype=np.float64)
    fills: list[Fill] = []

    for src_idx, dst_idx in zip(executable_idx, fill_idx):
        qty = float(target_delta[src_idx])
        if qty == 0.0:
            continue

        price = float(opens[dst_idx])
        if not np.isfinite(price):
            if gap_policy == GapPolicy.ERROR:
                raise ValueError(f"Missing next-bar open for fill at index {dst_idx}")
            # SKIP and EXPIRE are equivalent in this v1 baseline.
            continue

        executed_delta[dst_idx] = qty
        fills.append(
            Fill(
                timestamp_ms=int(ts[dst_idx]),
                symbol=symbol,
                quantity=abs(qty),
                price=price,
                side=OrderSide.BUY if qty > 0 else OrderSide.SELL,
            )
        )

    return fills, executed_delta
