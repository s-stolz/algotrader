from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ClosePositionDetail:
    entry_price: Decimal
    gross_profit: int
    swap: int
    commission: int
    balance: int
    quote_to_deposit_conversion_rate: Decimal | None = None
    closed_volume: int | None = None
    balance_version: int | None = None
    money_digits: int | None = None
    pnl_conversion_fee: int | None = None


@dataclass(frozen=True, slots=True)
class Deal:
    deal_id: int
    order_id: int
    position_id: int
    volume: int
    filled_volume: int
    symbol_id: int
    create_timestamp: int
    execution_timestamp: int
    trade_side: str
    deal_status: str
    utc_last_update_timestamp: int | None = None
    execution_price: Decimal | None = None
    margin_rate: Decimal | None = None
    commission: int | None = None
    base_to_usd_conversion_rate: Decimal | None = None
    close_position_detail: ClosePositionDetail | None = None
    money_digits: int | None = None
    label: str | None = None
    comment: str | None = None
    symbol: str | None = None
