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


class RecoverySource(BaseModel):
    symbol_id: int
    account_id: str

    @field_validator("account_id")
    @classmethod
    def validate_account(cls, value: str) -> str:
        if not value or len(value) > 128:
            raise ValueError("account_id must contain 1 to 128 characters")
        return value


class RecoveryBegin(RecoverySource):
    start_ms: int
    target_ms: int
    trigger: str

    @model_validator(mode="after")
    def validate_recovery(self):
        if self.start_ms < 0 or self.target_ms < self.start_ms - 1:
            raise ValueError("Recovery requires 0 <= start_ms <= target_ms + 1")
        if not self.trigger or len(self.trigger) > 64:
            raise ValueError("trigger must contain 1 to 64 characters")
        return self


class RecoveryAdvance(RecoverySource):
    recovery_id: str
    revision: int
    expected_start_ms: int
    next_ms: int

    @model_validator(mode="after")
    def validate_progress(self):
        if self.revision < 1 or not 0 <= self.expected_start_ms <= self.next_ms:
            raise ValueError("Recovery progress must advance the expected start")
        return self
