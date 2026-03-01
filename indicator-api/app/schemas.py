from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Metadata(BaseModel):
    id: int
    name: str
    overlay: bool
    inputs: Optional[List[str]] = []
    outputs: dict
    parameters: dict


class Candle(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorParameters(BaseModel):
    parameters: Optional[Dict[str, Any]] = {}
