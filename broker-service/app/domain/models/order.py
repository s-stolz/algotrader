from decimal import Decimal

from pydantic import BaseModel, Field

from ..value_objects import OrderType, TimeInForce

from .position import TradeData


class Order(BaseModel):
    # Required fields
    orderId: int = Field(
        alias="order_id",
        description="The unique ID of the order",
    )
    tradeData: TradeData = Field(
        alias="trade_data",
        description="Detailed trader data",
    )
    orderType: OrderType = Field(
        alias="order_type",
        description="Order type",
    )
    orderStatus: str = Field(
        alias="order_status",
        description="Order status",
    )
    # Optional execution details
    expirationTimestamp: int | None = Field(
        default=None,
        alias="expiration_timestamp",
        description="The Unix time in milliseconds of expiration (GTD orders)",
    )
    executionPrice: Decimal | None = Field(
        default=None,
        alias="execution_price",
        description="Price at which order was executed",
    )
    executedVolume: int | None = Field(
        default=None,
        alias="executed_volume",
        description="Part of the volume that was filled in cents",
    )
    utcLastUpdateTimestamp: int | None = Field(
        default=None,
        alias="utc_last_update_timestamp",
        description="The Unix time in milliseconds of the last update",
    )

    # Price levels
    baseSlippagePrice: Decimal | None = Field(
        default=None,
        alias="base_slippage_price",
        description="Used for Market Range order",
    )
    slippageInPoints: int | None = Field(
        default=None,
        alias="slippage_in_points",
        description="Price range for Market Range and STOP_LIMIT orders",
    )
    closingOrder: bool | None = Field(
        default=None,
        alias="closing_order",
        description="If TRUE, order is closing part of position",
    )
    limitPrice: Decimal | None = Field(
        default=None,
        alias="limit_price",
        description="Valid only for LIMIT orders",
    )
    stopPrice: Decimal | None = Field(
        default=None,
        alias="stop_price",
        description="Valid only for STOP and STOP_LIMIT orders",
    )
    stopLoss: Decimal | None = Field(
        default=None,
        alias="stop_loss",
        description="Absolute stopLoss price",
    )
    takeProfit: Decimal | None = Field(
        default=None,
        alias="take_profit",
        description="Absolute takeProfit price",
    )

    # Order metadata
    clientOrderId: str | None = Field(
        default=None,
        alias="client_order_id",
        description="Optional ClientOrderId (max 50 chars)",
    )
    timeInForce: TimeInForce | None = Field(
        default=None,
        alias="time_in_force",
        description="Order's time in force",
    )
    positionId: int | None = Field(
        default=None,
        alias="position_id",
        description="ID of the position linked to the order",
    )
    relativeStopLoss: int | None = Field(
        default=None,
        alias="relative_stop_loss",
        description="Relative stopLoss in 1/100000 of price unit",
    )
    relativeTakeProfit: int | None = Field(
        default=None,
        alias="relative_take_profit",
        description="Relative takeProfit in 1/100000 of price unit",
    )
    isStopOut: bool | None = Field(
        default=None,
        alias="is_stop_out",
        description="If TRUE, order was stopped out from server side",
    )
    trailingStopLoss: bool | None = Field(
        default=None,
        alias="trailing_stop_loss",
        description="If TRUE, order is trailingStopLoss",
    )
    stopTriggerMethod: str | None = Field(
        default=None,
        alias="stop_trigger_method",
        description="Trigger method for STOP and STOP_LIMIT orders",
    )

    # Convenience fields (not in protobuf)
    symbol: str | None = Field(
        default=None,
        description="Symbol name (convenience field)",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
        "json_encoders": {Decimal: float},
    }
