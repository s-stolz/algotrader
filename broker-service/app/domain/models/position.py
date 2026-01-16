from decimal import Decimal

from pydantic import BaseModel, Field


class TradeData(BaseModel):
    # Required fields
    symbolId: int = Field(
        alias="symbol_id",
        description="The unique identifier of the symbol",
    )
    volume: int = Field(
        description="Volume in cents (e.g. 1000 = 10.00 units)",
    )
    tradeSide: str = Field(
        alias="trade_side",
        description="Buy or Sell",
    )

    # Optional fields
    openTimestamp: int | None = Field(
        default=None,
        alias="open_timestamp",
        description="Unix time in ms when position was opened",
    )
    label: str | None = Field(
        default=None,
        description="Text label specified during order request",
    )
    guaranteedStopLoss: bool | None = Field(
        default=None,
        alias="guaranteed_stop_loss",
        description="If TRUE then position/order stop loss is guaranteed")
    comment: str | None = Field(
        default=None,
        description="User-specified comment",
    )
    measurementUnits: str | None = Field(
        default=None,
        alias="measurement_units",
        description="Units in which the symbol is denominated",
    )
    closeTimestamp: int | None = Field(
        default=None,
        alias="close_timestamp",
        description="Unix time in ms when position was closed",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
    }


class Position(BaseModel):
    # Required fields
    positionId: int = Field(
        alias="position_id",
        description="The unique ID of the position",
    )
    tradeData: TradeData = Field(
        alias="trade_data",
        description="Position details",
    )
    positionStatus: str = Field(
        alias="position_status",
        description="Current status of the position",
    )
    swap: int = Field(
        description="Total amount of charged swap on open position",
    )

    # Optional fields
    price: Decimal | None = Field(
        default=None,
        description="VWAP price based on all executions",
    )
    stopLoss: Decimal | None = Field(
        default=None,
        alias="stop_loss",
        description="Current stop loss price",
    )
    takeProfit: Decimal | None = Field(
        default=None,
        alias="take_profit",
        description="Current take profit price",
    )
    utcLastUpdateTimestamp: int | None = Field(
        default=None,
        alias="utc_last_update_timestamp",
        description="Unix time in ms of last change",
    )
    commission: int | None = Field(
        default=None,
        description="Current unrealized commission",
    )
    marginRate: Decimal | None = Field(
        default=None,
        alias="margin_rate",
        description="Rate for used margin computation (Base/Deposit)",
    )
    mirroringCommission: int | None = Field(
        default=None,
        alias="mirroring_commission",
        description="Unrealized commission for strategy following",
    )
    guaranteedStopLoss: bool | None = Field(
        default=None,
        alias="guaranteed_stop_loss",
        description="If TRUE then stop loss is guaranteed",
    )
    usedMargin: int | None = Field(
        default=None,
        alias="used_margin",
        description="Amount of margin used in deposit currency",
    )
    stopLossTriggerMethod: str | None = Field(
        default=None,
        alias="stop_loss_trigger_method",
        description="Stop trigger method for SL/TP",
    )
    moneyDigits: int | None = Field(
        default=None,
        alias="money_digits",
        description="Exponent for monetary values (e.g. 8 = 10^8)",
    )
    trailingStopLoss: bool | None = Field(
        default=None,
        alias="trailing_stop_loss",
        description="If TRUE then Trailing Stop Loss is applied",
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
