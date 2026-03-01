from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..value_objects import TradeSide


@dataclass(frozen=True, slots=True)
class Deal:
    id: int
    order_id: int
    position_id: int | None
    symbol: str
    symbol_id: int
    trade_side: TradeSide
    volume: int
    price: Decimal
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    commission: Decimal | None = None
    swap: Decimal | None = None
    created_at: int | None = None
