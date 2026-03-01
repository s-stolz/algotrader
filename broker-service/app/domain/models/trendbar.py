from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Trendbar:
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    v: int
    t: int
    digits: int = 5
