from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class LiveIndicatorStreamRequest(BaseModel):
    account_id: str
    symbol: str
    timeframe: str
    indicator_id: int
    exchange: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class LiveIndicatorWarmupInfo(BaseModel):
    required_bars: int
    seeded_bars: int
    source: Literal["cache", "database", "none", "existing"]


class LiveIndicatorStartResponse(BaseModel):
    stream_id: str
    redis_stream_key: str
    status: Literal["started", "already_running"]
    warmup: LiveIndicatorWarmupInfo


class LiveIndicatorStopResponse(BaseModel):
    stream_id: str
    stopped: bool


class LiveIndicatorStatusResponse(BaseModel):
    stream_id: str
    running: bool
    account_id: str
    symbol: str
    timeframe: str
    indicator_id: int
    exchange: Optional[str]
    ref_count: int
    redis_stream_key: str
