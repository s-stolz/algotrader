from typing import List

from pydantic import BaseModel, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class MarketIn(BaseModel):
    symbol: str
    exchange: str
    market_type: str
    min_move: float
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid IANA timezone: {value}") from exc
        return value


class MarketOut(MarketIn):
    symbol_id: int


class CandleIn(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleBatchIn(BaseModel):
    symbol: str
    exchange: str | None = None
    candles: List[CandleIn]


class HistoricalCandleBatchIn(CandleBatchIn):
    start_ms: int
    end_ms: int

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_ms > self.end_ms:
            raise ValueError("Historical interval must have start_ms <= end_ms")
        for candle in self.candles:
            if not self.start_ms <= candle.timestamp_ms <= self.end_ms:
                raise ValueError("Historical Candle lies outside the requested interval")
            if candle.timestamp_ms % 60000:
                raise ValueError("Historical M1 timestamps must be minute aligned")
        return self
