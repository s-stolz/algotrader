"""Domain-level enums for execution and event policies."""

from enum import Enum


class DataGranularity(str, Enum):
    BAR = "bar"
    TICK = "tick"


class SignalTiming(str, Enum):
    CLOSE = "close"


class FillTiming(str, Enum):
    NEXT_OPEN = "next_open"


class PriceSource(str, Enum):
    OPEN = "open"
    CLOSE = "close"


class GapPolicy(str, Enum):
    EXPIRE = "expire"
    SKIP = "skip"
    ERROR = "error"


class TradeAccountingPolicy(str, Enum):
    AVERAGE_COST = "average_cost"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class MarketEventType(str, Enum):
    BAR = "bar"
    TICK = "tick"
