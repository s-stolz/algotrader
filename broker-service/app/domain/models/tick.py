from pydantic import BaseModel, Field


class Tick(BaseModel):
    b: float = Field(
        description="Bid price",
    )
    a: float = Field(
        description="Ask price",
    )
    t: int = Field(
        description="Tick timestamp in milliseconds",
    )
    digits: int = Field(
        default=5,
        description="Number of decimal places for price formatting",
    )

    model_config = {
        "frozen": True,
    }
