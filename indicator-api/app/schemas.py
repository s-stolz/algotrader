from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class Metadata(BaseModel):
    id: int
    name: str
    overlay: bool
    inputs: Optional[List[str]] = []
    outputs: dict
    parameters: dict


class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorParameters(BaseModel):
    parameters: Optional[Dict[str, Any]] = {}
