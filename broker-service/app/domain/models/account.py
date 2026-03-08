from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Account:
    broker_name: str | None = None
    account_id: int = 0
    trader_login: int | None = None
    currency: int | None = None
    balance: Decimal = Decimal("0")
    access_rights: str | None = None
    leverage: int | None = None
    max_leverage: int | None = None
    is_live: bool = False
    money_digits: int = 2
