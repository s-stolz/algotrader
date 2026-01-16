from pydantic import BaseModel, Field


class Symbol(BaseModel):
    symbol_id: int = Field(
        ...,
        description="cTrader symbol id",
    )
    symbol_name: str = Field(
        ...,
        description="Symbol name, e.g. EURUSD",
    )
    digits: int = Field(
        ...,
        description="Price decimal digits",
    )
    pip_position: int = Field(
        ...,
        description="Pip position in price",
    )
    commission: int = Field(
        default=0,
        description="Commission base amount (use preciseTradingCommissionRate for precision)",
    )
    commission_type: str | None = Field(
        default=None,
        description="Commission type: USD_PER_MILLION_USD, USD_PER_LOT, PERCENTAGE_OF_VALUE, QUOTE_CCY_PER_LOT",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
    }
