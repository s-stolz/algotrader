from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.models import Symbol
from app.domain.value_objects import (
    OrderType,
    TickStreamOptions,
    TradeSide,
)


class SymbolLightResponse(BaseModel):
    symbol_id: int = Field(..., alias="symbolId", description="Numeric cTrader symbol id")
    symbol_name: str = Field(..., alias="symbolName", description="Symbol display name")
    enabled: bool | None = Field(default=None, description="Whether symbol is tradable")

    model_config = {
        "populate_by_name": True,
    }


class SymbolResponse(Symbol):

    model_config = {
        "populate_by_name": True,
    }


class OrderRequest(BaseModel):
    symbol: str = Field(..., description="Symbol name, e.g. EURUSD")
    order_type: OrderType = Field(
        ...,
        alias="orderType",
        description="Order type (MARKET/LIMIT/STOP/...)",
    )
    trade_side: TradeSide = Field(
        ...,
        alias="tradeSide",
        description="BUY or SELL",
    )
    volume: int = Field(..., description="Volume in lots * 100 (e.g. 100 = 0.01 lot)")
    limit_price: float | None = Field(
        default=None,
        alias="limitPrice",
        description="Limit price for LIMIT orders",
    )
    stop_price: float | None = Field(
        default=None,
        alias="stopPrice",
        description="Stop price for STOP / STOP_LIMIT orders",
    )
    stop_loss: float | None = Field(default=None, alias="stopLoss")
    take_profit: float | None = Field(default=None, alias="takeProfit")
    time_in_force: str | None = Field(default=None, alias="timeInForce")
    expiration_timestamp: int | None = Field(
        default=None,
        alias="expirationTimestamp",
        description="Optional expiration in epoch millis",
    )
    comment: str | None = None
    label: str | None = None
    client_order_id: str | None = Field(default=None, alias="clientOrderId")

    model_config = {
        "populate_by_name": True,
    }


class ClosePositionRequest(BaseModel):
    close_quantity: int | None = Field(
        default=None,
        alias="closeQuantity",
        description="Quantity to close in trade units (volume * 100). None closes full position",
    )

    model_config = {
        "populate_by_name": True,
    }


class TickStreamRequest(BaseModel):
    queue_size: int | None = Field(default=None, alias="queueSize", ge=1)
    max_stream_length: int | None = Field(
        default=None,
        alias="maxStreamLength",
        ge=100,
    )

    def as_options(self) -> TickStreamOptions:
        return TickStreamOptions(
            queue_size=self.queue_size,
            max_stream_length=self.max_stream_length,
        )

    model_config = {
        "populate_by_name": True,
    }


class TickStreamStatusResponse(BaseModel):
    running: bool
    started_at: float | None = Field(default=None, alias="startedAt")
    last_tick_at: float | None = Field(default=None, alias="lastTickAt")
    uptime_seconds: float | None = Field(default=None, alias="uptimeSeconds")
    error: str | None = None

    model_config = {
        "populate_by_name": True,
    }


class HealthComponent(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    components: dict[str, HealthComponent]


class TrendbarStreamStatusResponse(BaseModel):
    running: bool
    started_at: float | None = Field(default=None, alias="startedAt")
    last_bar_at: float | None = Field(default=None, alias="lastBarAt")
    uptime_seconds: float | None = Field(default=None, alias="uptimeSeconds")
    error: str | None = None

    model_config = {
        "populate_by_name": True,
    }


class TrendbarResponse(BaseModel):
    """Trendbar response excluding internal fields like digits."""

    o: Decimal = Field(description="Open price")
    h: Decimal = Field(description="High price")
    l: Decimal = Field(description="Low price")
    c: Decimal = Field(description="Close price")
    v: int = Field(description="Volume")
    t: int = Field(description="Bar closing timestamp in epoch millis")

    model_config = {
        "json_encoders": {Decimal: float},
    }
