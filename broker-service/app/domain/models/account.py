from decimal import Decimal

from pydantic import BaseModel, Field


class Account(BaseModel):
    broker_name: str | None = Field(
        default=None,
        description="Name of the broker that owns the account",
    )
    account_id: int = Field(
        description="cTrader trader account id",
    )
    trader_login: int | None = Field(
        default=None,
        description="ID of the account that is unique per server (Broker)",
    )
    currency: int | None = Field(
        default=None,
        description="Deposit currency of the account",
    )
    balance: Decimal = Field(
        description="Current balance in deposit currency",
    )
    access_rights: str | None = Field(
        default=None,
        description="Account access rights as string",
    )
    leverage: int | None = Field(
        default=None,
        description="Account leverage",
    )
    max_leverage: int | None = Field(
        default=None,
        description="Maximum allowed leverage for the account",
    )
    is_live: bool = Field(
        default=False,
        description="True if account belongs to live environment",
    )
    money_digits: int = Field(
        default=2,
        description="Digits used for monetary conversions",
    )

    model_config = {
        "arbitrary_types_allowed": True,
        "frozen": True,
        "json_encoders": {Decimal: float},
    }
