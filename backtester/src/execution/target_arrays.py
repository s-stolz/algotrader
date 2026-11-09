"""Array selection of sized-target execution events between strategy decisions."""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from execution.orders import OrderExecutionConfig, OrderExecutionState


@dataclass
class TargetExecutionArrays:
    timestamp_ms: NDArray[np.int64]
    prices: NDArray[np.float64]
    signals: NDArray[np.int64]
    boundaries: NDArray[np.int64]
    targets: NDArray[np.float64]
    decision_indices: NDArray[np.int64] = field(init=False)
    invalid_indices: NDArray[np.int64] = field(init=False)
    previous_valid_indices: NDArray[np.int64] = field(init=False)

    def __post_init__(self) -> None:
        count = self.timestamp_ms.size
        if self.prices.shape != (count, 4) or any(
            values.shape != (count,) for values in (self.signals, self.boundaries, self.targets)
        ):
            raise ValueError("Sized target execution arrays must have equal lengths")
        opening, high, low, closing = self.prices.T
        valid = (
            np.all(np.isfinite(self.prices) & (self.prices > 0), axis=1)
            & (low <= np.minimum(opening, closing))
            & (np.maximum(opening, closing) <= high)
        )
        self.decision_indices = np.flatnonzero(self.signals)
        self.invalid_indices = np.flatnonzero(~valid)
        self.previous_valid_indices = np.maximum.accumulate(np.where(valid, np.arange(count), -1))

    def next_event(
        self, start: int, state: OrderExecutionState, config: OrderExecutionConfig
    ) -> int:
        """Locate the next state-changing bar without interpreting quiet bars.

        Sizing is path dependent, so masks are bounded by the next decision or
        pending fill. Protective/depletion thresholds stay constant within each
        interval and can be matched against entire OHLC slices at once.
        """
        count = self.timestamp_ms.size
        if start >= count or state.active:
            return start
        end = min(
            self._next_index(self.decision_indices, start),
            self._next_index(self.invalid_indices, start),
        )
        if not state.position:
            return end
        if config.daily_schedule is not None and state.entry_timestamp_ms is not None:
            deadline = config.daily_schedule.exit_timestamp(state.entry_timestamp_ms)
            end = min(end, max(start, int(np.searchsorted(self.timestamp_ms, deadline))))
        stop = min(end + 1, count)
        high, low = self.prices[start:stop, 1], self.prices[start:stop, 2]
        long = state.position > 0
        touched = np.zeros(stop - start, dtype=bool)
        if state.stop_price is not None:
            touched |= low <= state.stop_price if long else high >= state.stop_price
        for price, _ in state.targets:
            touched |= high >= price if long else low <= price
        assert config.instrument is not None
        worst_price = low if long else high
        touched |= (
            config.initial_capital
            + state.cash
            + state.position * worst_price * config.instrument.contract_multiplier
        ) <= 1e-9
        matches = np.flatnonzero(touched)
        return start + int(matches[0]) if matches.size else end

    def _next_index(self, indices: NDArray[np.int64], start: int) -> int:
        offset = int(np.searchsorted(indices, start))
        return int(indices[offset]) if offset < indices.size else self.timestamp_ms.size
