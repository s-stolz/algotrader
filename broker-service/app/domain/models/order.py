from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..value_objects import OrderType, TimeInForce
from .position import TradeData


@dataclass(frozen=True, slots=True)
class Order:
    order_id: int
    trade_data: TradeData
    order_type: OrderType | str
    order_status: str
    expiration_timestamp: int | None = None
    execution_price: Decimal | None = None
    executed_volume: int | None = None
    utc_last_update_timestamp: int | None = None
    base_slippage_price: Decimal | None = None
    slippage_in_points: int | None = None
    closing_order: bool | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    client_order_id: str | None = None
    time_in_force: TimeInForce | str | None = None
    position_id: int | None = None
    relative_stop_loss: int | None = None
    relative_take_profit: int | None = None
    is_stop_out: bool | None = None
    trailing_stop_loss: bool | None = None
    stop_trigger_method: str | None = None
    symbol: str | None = None
