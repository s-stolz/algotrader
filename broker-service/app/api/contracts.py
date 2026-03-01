from __future__ import annotations

from typing import NotRequired, TypedDict


class OrderRequestBody(TypedDict):
    symbol: str
    orderType: str
    tradeSide: str
    volume: int
    limitPrice: NotRequired[float]
    stopPrice: NotRequired[float]
    stopLoss: NotRequired[float]
    takeProfit: NotRequired[float]
    timeInForce: NotRequired[str]
    expirationTimestamp: NotRequired[int]
    comment: NotRequired[str]
    label: NotRequired[str]
    clientOrderId: NotRequired[str]


class ClosePositionRequestBody(TypedDict):
    closeQuantity: NotRequired[int]


class TickStreamStatusBody(TypedDict):
    running: bool
    startedAt: float | None
    lastTickAt: float | None
    uptimeSeconds: float | None
    error: str | None


class TrendbarStreamStatusBody(TypedDict):
    running: bool
    startedAt: float | None
    lastBarAt: float | None
    uptimeSeconds: float | None
    error: str | None


class SymbolLightBody(TypedDict):
    symbolId: int
    symbolName: str
    enabled: bool | None


ORDER_REQUEST_SCHEMA = {
    "type": "object",
    "required": ["symbol", "orderType", "tradeSide", "volume"],
    "properties": {
        "symbol": {"type": "string", "description": "Symbol name, e.g. EURUSD"},
        "orderType": {"type": "string"},
        "tradeSide": {"type": "string"},
        "volume": {"type": "integer", "description": "Volume in lots * 100 (e.g. 100 = 0.01 lot)"},
        "limitPrice": {"type": ["number", "null"]},
        "stopPrice": {"type": ["number", "null"]},
        "stopLoss": {"type": ["number", "null"]},
        "takeProfit": {"type": ["number", "null"]},
        "timeInForce": {"type": ["string", "null"]},
        "expirationTimestamp": {"type": ["integer", "null"]},
        "comment": {"type": ["string", "null"]},
        "label": {"type": ["string", "null"]},
        "clientOrderId": {"type": ["string", "null"]},
    },
}

CLOSE_POSITION_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "closeQuantity": {
            "type": ["integer", "null"],
            "description": "Quantity to close in trade units (volume * 100). None closes full position",
        }
    },
}
