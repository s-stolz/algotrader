from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TradeData:
    symbol_id: int
    volume: int
    trade_side: str
    open_timestamp: int | None = None
    label: str | None = None
    guaranteed_stop_loss: bool | None = None
    comment: str | None = None
    measurement_units: str | None = None
    close_timestamp: int | None = None


@dataclass(frozen=True, slots=True)
class Position:
    position_id: int
    trade_data: TradeData
    position_status: str
    swap: int
    price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    utc_last_update_timestamp: int | None = None
    commission: int | None = None
    margin_rate: Decimal | None = None
    mirroring_commission: int | None = None
    guaranteed_stop_loss: bool | None = None
    used_margin: int | None = None
    stop_loss_trigger_method: str | None = None
    money_digits: int | None = None
    trailing_stop_loss: bool | None = None
    symbol: str | None = None
