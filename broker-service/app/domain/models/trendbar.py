from decimal import Decimal

from pydantic import BaseModel, Field


class Trendbar(BaseModel):
    o: Decimal = Field(
        description="Open price",
    )
    h: Decimal = Field(
        description="High price",
    )
    l: Decimal = Field(
        description="Low price",
    )
    c: Decimal = Field(
        description="Close price",
    )
    v: int = Field(
        description="Volume in ticks or lots depending on broker",
    )
    t: int = Field(
        description="Bar closing timestamp in epoch millis",
    )
    digits: int = Field(
        default=5,
        description="Number of decimal places for price formatting",
    )

    model_config = {
        "frozen": True,
        "json_encoders": {Decimal: float},
    }
