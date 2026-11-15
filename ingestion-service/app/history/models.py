from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MINIMUM_HISTORY_DATE = date(1970, 1, 1)
MAXIMUM_CANDLE_COUNT = 1_000_000


class HistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    market_id: int = Field(gt=0, strict=True)
    start_date: str | None = None
    candle_count: int | None = Field(default=None, gt=0, le=MAXIMUM_CANDLE_COUNT, strict=True)

    @model_validator(mode="after")
    def validate_selector(self) -> Self:
        if (self.start_date is None) == (self.candle_count is None):
            raise ValueError("Choose a start date or a number of additional one-minute candles")
        if self.start_date is not None:
            parsed = date.fromisoformat(self.start_date)
            if parsed.isoformat() != self.start_date or parsed < MINIMUM_HISTORY_DATE:
                raise ValueError("Start date must use YYYY-MM-DD and be on or after 1970-01-01")
            if parsed > datetime.now(timezone.utc).date():
                raise ValueError("Start date cannot be in the future")
        return self

    def storage_payload(self) -> dict:
        start_ms = None
        if self.start_date is not None:
            start_ms = int(
                datetime.combine(
                    date.fromisoformat(self.start_date), datetime.min.time(), timezone.utc
                ).timestamp()
                * 1000
            )
        return {
            "request_id": str(self.request_id),
            "market_id": self.market_id,
            "start_ms": start_ms,
            "candle_count": self.candle_count,
        }


def public_snapshot(job: dict) -> dict:
    return {
        key: value
        for key, value in job.items()
        if key not in {"owner_token", "lease_expires_at", "first_inserted_ms", "last_inserted_ms"}
    }
