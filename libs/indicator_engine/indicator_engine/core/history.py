"""History policies for rolling and unbounded buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UTC_DAY_MS = 86_400_000


@dataclass(frozen=True)
class InputHistoryPlan:
    """Fetch calculation rows from start_ms and predecessors strictly before it.

    Predecessors are available candles, not synthetic timeframe slots. Callers
    retain their original output bounds and trim only after calculation.
    """

    start_ms: int
    predecessor_bars: int = 0


@dataclass(frozen=True)
class InputHistory:
    """Calculation history, independent of output warmup and buffer retention."""

    anchor: Literal["rolling", "utc_day"] = "rolling"
    predecessor_bars: int = 0

    def __post_init__(self) -> None:
        if self.anchor not in ("rolling", "utc_day"):
            raise ValueError(f"Invalid history anchor: {self.anchor}")
        if self.predecessor_bars < 0:
            raise ValueError("predecessor_bars must be nonnegative")

    def plan(self, *, start_ms: int, warmup_bars: int) -> InputHistoryPlan:
        """Resolve a fetch anchor without guessing across market closures."""
        if warmup_bars < 1:
            raise ValueError("warmup_bars must be positive")
        if self.anchor == "utc_day":
            return InputHistoryPlan(
                start_ms=(start_ms // UTC_DAY_MS) * UTC_DAY_MS,
                predecessor_bars=self.predecessor_bars,
            )
        return InputHistoryPlan(
            start_ms=start_ms,
            predecessor_bars=max(warmup_bars - 1, self.predecessor_bars),
        )


@dataclass(frozen=True)
class HistoryPolicy:
    """Controls how many rows a buffer retains.

    mode:
        - "rolling": keep only the last max_rows entries.
        - "unbounded": grow as needed (optionally with initial max_rows capacity).
    """

    mode: Literal["unbounded", "rolling"] = "rolling"
    max_rows: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("unbounded", "rolling"):
            raise ValueError(f"Invalid mode: {self.mode}")
        if self.mode == "rolling":
            if self.max_rows is None or self.max_rows <= 0:
                raise ValueError("rolling mode requires max_rows > 0")
        if self.max_rows is not None and self.max_rows <= 0:
            raise ValueError("max_rows must be > 0 when provided")
