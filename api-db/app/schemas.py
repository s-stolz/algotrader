# app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import List


class MarketIn(BaseModel):
    symbol: str
    exchange: str
    market_type: str
    min_move: float


class MarketOut(MarketIn):
    symbol_id: int


class CandleIn(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleBatchIn(BaseModel):
    symbol: str
    exchange: str = "%"
    candles: List[CandleIn]
