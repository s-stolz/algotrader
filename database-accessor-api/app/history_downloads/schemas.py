from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AcceptJob(JobInput):
    request_id: UUID
    market_id: StrictInt = Field(gt=0)
    start_ms: StrictInt | None = Field(default=None, ge=0)
    candle_count: StrictInt | None = Field(default=None, gt=0, le=10_000_000)

    @model_validator(mode="after")
    def validate_selector(self) -> "AcceptJob":
        if (self.start_ms is None) == (self.candle_count is None):
            raise ValueError("Choose a start date or an additional candle count")
        if self.start_ms is not None and self.start_ms % 60000:
            raise ValueError("Historical start must be minute aligned")
        return self


class ClaimJob(JobInput):
    owner_token: str = Field(min_length=1, max_length=128)
    lease_seconds: StrictInt = Field(default=120, ge=10, le=3600)


class OwnedJob(JobInput):
    owner_token: str = Field(min_length=1, max_length=128)
    revision: StrictInt = Field(gt=0)


class HeartbeatJob(OwnedJob):
    lease_seconds: StrictInt = Field(default=120, ge=10, le=3600)


class ExtensionCandle(JobInput):
    timestamp_ms: StrictInt = Field(ge=0)
    open: float
    high: float
    low: float
    close: float
    volume: float

    @field_validator("timestamp_ms")
    @classmethod
    def validate_minute(cls, value: int) -> int:
        if value % 60000:
            raise ValueError("Historical candles must be minute aligned")
        return value


class CommitPage(OwnedJob):
    expected_cursor_ms: StrictInt = Field(ge=0)
    next_cursor_ms: StrictInt = Field(ge=0)
    fetched_count: StrictInt = Field(ge=0, le=4000)
    candles: list[ExtensionCandle] = Field(max_length=4000)

    @model_validator(mode="after")
    def validate_page(self) -> "CommitPage":
        if self.next_cursor_ms >= self.expected_cursor_ms:
            raise ValueError("Historical cursor must move backwards")
        if self.next_cursor_ms % 60000 or self.expected_cursor_ms % 60000:
            raise ValueError("Historical cursor must be minute aligned")
        timestamps = {candle.timestamp_ms for candle in self.candles}
        if len(timestamps) != len(self.candles) or self.fetched_count != len(timestamps):
            raise ValueError("Fetched count must equal the distinct supplied candles")
        if any(not self.next_cursor_ms <= value < self.expected_cursor_ms for value in timestamps):
            raise ValueError("Candles must belong to the confirmed cursor interval")
        return self


class TransitionJob(OwnedJob):
    status: Literal["completed", "failed", "queued"]
    failure_reason: str | None = Field(default=None, max_length=2000)
    availability_reason: str | None = Field(default=None, max_length=2000)
