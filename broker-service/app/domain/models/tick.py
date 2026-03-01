from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tick:
    b: float
    a: float
    t: int
    digits: int = 5
