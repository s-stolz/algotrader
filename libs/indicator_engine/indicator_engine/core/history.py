"""History policies for rolling and unbounded buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
