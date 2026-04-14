"""Fill generation for vectorized backtest execution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from domain.enums import GapPolicy, OrderSide
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

    if ts.size != opens.size or ts.size != target.size:
        raise ValueError("timestamp, open price, and target arrays must have equal length")

    if not np.isfinite(slippage_bps):
        raise ValueError("slippage_bps must be finite")
    if slippage_bps < 0.0:
        raise ValueError("slippage_bps must be >= 0")
    if not np.isfinite(commission_bps):
        raise ValueError("commission_bps must be finite")
    if commission_bps < 0.0:
        raise ValueError("commission_bps must be >= 0")

    if ts.size == 0:
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

    previous_target = np.concatenate(([0.0], target[:-1]))
    target_delta = target - previous_target

    executed_delta = np.zeros_like(target, dtype=np.float64)
    executed_notional = np.zeros_like(target, dtype=np.float64)
    executed_fees = np.zeros_like(target, dtype=np.float64)
    fills: list[Fill] = []

    pending: list[_PendingDelta] = []

    total_slippage_cost = 0.0
    invalid_open_count = 0
    deferred_delta_count = 0
    expired_delta_count = 0
    executed_deferred_count = 0

    for dst_idx in range(1, ts.size):
        src_idx = dst_idx - 1
        decision_delta = float(target_delta[src_idx])
        if decision_delta != 0.0:
            pending.append(_PendingDelta(quantity=decision_delta))

        if not pending:
            continue

        pending_total = float(sum(item.quantity for item in pending))
        if pending_total == 0.0:
            pending.clear()
            continue

        raw_open = float(opens[dst_idx])
        if _is_valid_open(raw_open):
            executed_delta[dst_idx] = pending_total
            side = OrderSide.BUY if pending_total > 0 else OrderSide.SELL
            quantity = abs(pending_total)
            execution_price = _apply_slippage(
                raw_open=raw_open,
                side=side,
                slippage_bps=slippage_bps,
            )
            fee = quantity * execution_price * (commission_bps / 10_000.0)

            fills.append(
                Fill(
                    timestamp_ms=int(ts[dst_idx]),
                    symbol=symbol,
                    quantity=quantity,
                    price=execution_price,
                    side=side,
                    fees=float(fee),
                )
            )

            executed_notional[dst_idx] = pending_total * execution_price
            executed_fees[dst_idx] = float(fee)
            total_slippage_cost += quantity * abs(execution_price - raw_open)
            executed_deferred_count += sum(
                1 for item in pending if item.deferred and item.quantity != 0.0
            )
            pending.clear()
            continue

        invalid_open_count += 1
        if gap_policy == GapPolicy.ERROR:
            raise ValueError(
                "Missing valid next-bar open for pending fill(s) "
                f"at index {dst_idx} and timestamp {int(ts[dst_idx])}"
            )

        if gap_policy == GapPolicy.EXPIRE:
            expired_delta_count += sum(1 for item in pending if item.quantity != 0.0)
            pending.clear()
            continue

        for item in pending:
            if item.quantity != 0.0 and not item.deferred:
                item.deferred = True
                deferred_delta_count += 1

    # Decision on the final bar has no in-range next-open and therefore expires.
    final_delta = float(target_delta[-1])
    if final_delta != 0.0:
        pending.append(_PendingDelta(quantity=final_delta))

    tail_expired_delta_count = 0
    if pending:
        pending_total = float(sum(item.quantity for item in pending))
        if pending_total != 0.0:
            tail_expired_delta_count = sum(1 for item in pending if item.quantity != 0.0)

    return FillGenerationResult(
        fills=fills,
        executed_delta=executed_delta,
        executed_notional=executed_notional,
        executed_fees=executed_fees,
        total_slippage_cost=float(total_slippage_cost),
        invalid_open_count=invalid_open_count,
        deferred_delta_count=deferred_delta_count,
        expired_delta_count=expired_delta_count,
        executed_deferred_count=executed_deferred_count,
        tail_expired_delta_count=tail_expired_delta_count,
    )


def _is_valid_open(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _apply_slippage(*, raw_open: float, side: OrderSide, slippage_bps: float) -> float:
    factor = slippage_bps / 10_000.0
    if side == OrderSide.BUY:
        return float(raw_open * (1.0 + factor))
    return float(raw_open * (1.0 - factor))
