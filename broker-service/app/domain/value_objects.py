from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType

AccountId = NewType("AccountId", int)
OrderId = NewType("OrderId", int)
PositionId = NewType("PositionId", int)
SymbolId = NewType("SymbolId", int)


@dataclass(slots=True)
class SymbolDescriptor:
    """Light symbol info for listing (from ProtoOASymbolsListRes)."""

    symbol_id: SymbolId
    symbol_name: str
    enabled: bool | None = None


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    STOP_LOSS_TAKE_PROFIT = "STOP_LOSS_TAKE_PROFIT"
    MARKET_RANGE = "MARKET_RANGE"


class TimeInForce(str, Enum):
    GOOD_TILL_DATE = "GOOD_TILL_DATE"
    GOOD_TILL_CANCEL = "GOOD_TILL_CANCEL"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"
    MARKET_ON_OPEN = "MARKET_ON_OPEN"


class Timeframe(str, Enum):
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M10 = "M10"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    H12 = "H12"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


@dataclass(slots=True)
class TickStreamOptions:
    queue_size: int | None = None
    max_stream_length: int | None = None


@dataclass(slots=True)
class TickStreamStatus:
    running: bool
    started_at: float | None
    last_tick_at: float | None
    uptime_seconds: float | None
    error: str | None = None


@dataclass(slots=True)
class TrendbarStreamOptions:
    """Options for trendbar streaming."""
    only_completed_bars: bool = True
    """If True (default), only publish bars when they close (new timestamp).
    If False, publish every live update (on each tick)."""


@dataclass(slots=True)
class TrendbarStreamStatus:
    running: bool
    started_at: float | None
    last_bar_at: float | None
    uptime_seconds: float | None
    error: str | None = None
