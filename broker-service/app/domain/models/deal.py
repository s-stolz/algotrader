from decimal import Decimal

from pydantic import BaseModel, Field


class ClosePositionDetail(BaseModel):
    # Required fields
    entryPrice: Decimal = Field(
        alias="entry_price",
        description="Position price at the moment of filling the closing order",
    )
    grossProfit: int = Field(
        alias="gross_profit",
        description="Amount of realized gross profit after closing deal execution",
    )
    swap: int = Field(
        description="Amount of realized swap related to closed volume",
    )
    commission: int = Field(
        description="Amount of realized commission related to closed volume",
    )
    balance: int = Field(
        description="Account balance after closing deal execution",
    )

    # Optional fields
    quoteToDepositConversionRate: Decimal | None = Field(
        default=None,
        alias="quote_to_deposit_conversion_rate",
        description="Quote/Deposit currency conversion rate on the time of closing deal execution",
    )
    closedVolume: int | None = Field(
        default=None,
        alias="closed_volume",
        description="Closed volume in cents",
    )
    balanceVersion: int | None = Field(
        default=None,
        alias="balance_version",
        description="Balance version of the account related to closing deal operation",
    )
    moneyDigits: int | None = Field(
        default=None,
        alias="money_digits",
        description="Specifies the exponent of the monetary values",
    )
    pnlConversionFee: int | None = Field(
        default=None,
        alias="pnl_conversion_fee",
        description="Fee for conversion applied to the Deal in account's ccy",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
        "json_encoders": {Decimal: float},
    }


class Deal(BaseModel):
    # Required fields
    dealId: int = Field(
        alias="deal_id",
        description="The unique ID of the execution deal",
    )
    orderId: int = Field(
        alias="order_id",
        description="Source order of the deal",
    )
    positionId: int = Field(
        alias="position_id",
        description="Source position of the deal",
    )
    volume: int = Field(
        description="Volume sent for execution, in cents",
    )
    filledVolume: int = Field(
        alias="filled_volume",
        description="Filled volume, in cents",
    )
    symbolId: int = Field(
        alias="symbol_id",
        description="The unique identifier of the symbol",
    )
    createTimestamp: int = Field(
        alias="create_timestamp",
        description="The Unix time in milliseconds when the deal was sent for execution",
    )
    executionTimestamp: int = Field(
        alias="execution_timestamp",
        description="The Unix time in milliseconds when the deal was executed",
    )
    tradeSide: str = Field(
        alias="trade_side",
        description="Buy/Sell",
    )
    dealStatus: str = Field(
        alias="deal_status",
        description="Status of the deal",
    )

    # Optional fields
    utcLastUpdateTimestamp: int | None = Field(
        default=None,
        alias="utc_last_update_timestamp",
        description="The Unix time in milliseconds when the deal was created, executed or rejected",
    )
    executionPrice: Decimal | None = Field(
        default=None,
        alias="execution_price",
        description="Execution price",
    )
    marginRate: Decimal | None = Field(
        default=None,
        alias="margin_rate",
        description="Rate for used margin computation. Represented as Base/Deposit",
    )
    commission: int | None = Field(
        default=None,
        description="Amount of trading commission associated with the deal",
    )
    baseToUsdConversionRate: Decimal | None = Field(
        default=None,
        alias="base_to_usd_conversion_rate",
        description="Base to USD conversion rate on the time of deal execution",
    )
    closePositionDetail: ClosePositionDetail | None = Field(
        default=None,
        alias="close_position_detail",
        description="Closing position detail. Valid only for closing deal",
    )
    moneyDigits: int | None = Field(
        default=None,
        alias="money_digits",
        description="Specifies the exponent of the monetary values",
    )
    label: str | None = Field(
        default=None,
        description="Label field value from corresponding order",
    )
    comment: str | None = Field(
        default=None,
        description="Comment field value from corresponding order",
    )

    # Convenience fields (not in ProtoOADeal but useful for responses)
    symbol: str | None = Field(
        default=None,
        description="Symbol name (derived from symbolId)",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
        "json_encoders": {Decimal: float},
    }
