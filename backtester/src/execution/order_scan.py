"""Array-facing minute execution scan; strategy calculations stay outside the scan."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from domain.enums import GapPolicy
from domain.orders import OrderCommand
from domain.types import Fill
from numpy.typing import NDArray

from execution.orders import OrderExecutionConfig, OrderExecutionState, execute_minute


@dataclass(frozen=True)
class OrderScanResult:
    fills: list[Fill]
    executed_delta: NDArray[np.float64]
    executed_notional: NDArray[np.float64]
    executed_fees: NDArray[np.float64]
    events: list[dict[str, object]]
    ambiguous_minutes: int


def scan_orders(  # noqa: C901
    *,
    symbol: str,
    timestamp_ms: Sequence[int],
    ohlc: NDArray[np.float64],
    commands: Sequence[OrderCommand],
    end_ms: int,
    config: OrderExecutionConfig,
    start_ms: int | None = None,
) -> OrderScanResult:
    """Merge sorted close-time commands into minute bars without a nested time scan.

    Only currently active orders are visited during matching. Historical fills and
    diagnostics are accumulated outside the matcher to keep scan cost linear in
    execution minutes plus matching work, rather than total historical fills.
    """
    timestamps = np.asarray(timestamp_ms, dtype=np.int64)
    if ohlc.shape != (len(timestamps), 4):
        raise ValueError("ohlc must have one open/high/low/close row per timestamp")
    if np.any(timestamps % 60_000) or np.any(np.diff(timestamps) <= 0):
        raise ValueError("execution timestamps must be unique increasing minute boundaries")
    if len(timestamps) and timestamps[-1] >= end_ms:
        raise ValueError("execution bars must precede end_ms")
    ordered = sorted(commands, key=lambda command: command.effective_at_ms)
    state = OrderExecutionState(config=config)
    fills: list[Fill] = []
    events: list[dict[str, object]] = []
    delta, notional, fees = (np.zeros(len(timestamps), dtype=np.float64) for _ in range(3))
    cursor = 0
    previous_end = int(timestamps[0]) if start_ms is None and len(timestamps) else (start_ms or 0)
    for index, timestamp in enumerate(timestamps):
        while cursor < len(ordered) and ordered[cursor].effective_at_ms < timestamp:
            state.command(ordered[cursor])
            cursor += 1
        if timestamp > previous_end:
            if config.gap_policy == GapPolicy.ERROR:
                raise ValueError(f"Missing minute execution data at {previous_end}")
            state.record(previous_end, "", "execution_gap")
            if config.gap_policy == GapPolicy.EXPIRE:
                for key in state.active:
                    state.record(previous_end, key, "gap_expired")
                state.active.clear()
        while cursor < len(ordered) and ordered[cursor].effective_at_ms == timestamp:
            state.command(ordered[cursor])
            cursor += 1
        previous_end = int(timestamp) + 60_000
        state = execute_minute(
            state, symbol=symbol, timestamp_ms=int(timestamp), prices=ohlc[index], config=config
        )
        for fill in state.fills:
            signed = fill.quantity if fill.side.value == "buy" else -fill.quantity
            delta[index] += signed
            notional[index] += (
                signed
                * fill.price
                * (config.instrument.contract_multiplier if config.instrument else 1.0)
            )
            fees[index] += fill.fees
        fills.extend(state.fills)
        events.extend(state.events)
        state.fills = []
        state.events = []
        if state.depleted:
            break
    if previous_end < end_ms and not state.depleted:
        if config.gap_policy == GapPolicy.ERROR:
            raise ValueError(f"Missing minute execution data at {previous_end}")
        state.record(previous_end, "", "execution_gap")
    for key in state.active:
        state.record(end_ms, key, "run_end_expired")
    for command in [] if state.depleted else ordered[cursor:]:
        state.record(end_ms, command.order_id, "run_end_unexecuted")
    events.extend(state.events)
    return OrderScanResult(fills, delta, notional, fees, events, state.ambiguous_minutes)
