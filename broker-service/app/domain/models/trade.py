from decimal import Decimal

from pydantic import BaseModel, Field

from ..value_objects import TradeSide


class Deal(BaseModel):
    id: int = Field(
        description="Deal id",
    )
    order_id: int = Field(
        description="Order id that created the deal",
    )
    position_id: int | None = Field(
        default=None,
    )
    symbol: str = Field(
        description="Symbol name",
    )
    symbol_id: int = Field(
        description="cTrader symbol id",
    )
    trade_side: TradeSide = Field(
        description="BUY/SELL",
    )
    volume: int = Field(
        description="Filled volume",
    )
    price: Decimal = Field(
        description="Execution price",
    )
    gross_pnl: Decimal | None = Field(
        default=None,
    )
    net_pnl: Decimal | None = Field(
        default=None,
    )
    commission: Decimal | None = Field(
        default=None,
    )
    swap: Decimal | None = Field(
        default=None,
    )
    created_at: int | None = Field(
        default=None,
        description="Epoch millis",
    )

    model_config = {
        "frozen": True,
        "json_encoders": {Decimal: float},
    }
