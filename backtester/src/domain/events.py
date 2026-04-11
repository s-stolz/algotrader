"""Domain events used by event-driven engines."""

from dataclasses import dataclass

from domain.enums import MarketEventType


@dataclass(frozen=True)
class BarEvent:
    timestamp_ms: int
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    event_type: MarketEventType = MarketEventType.BAR


@dataclass(frozen=True)
class TickEvent:
    timestamp_ms: int
    symbol: str
    bid: float
    ask: float
    last: float
    size: float
    event_type: MarketEventType = MarketEventType.TICK
