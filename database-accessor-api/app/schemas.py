from datetime import datetime
from typing import List

from pydantic import BaseModel, field_validator
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


class BacktestRunSummaryIn(BaseModel):
    execution_duration_ms: int
    symbol: str
    timeframe: str
    engine: str
    strategy_id: str
    start_ms: int
    end_ms: int
    initial_capital: float
    final_equity: float
    final_cash: float
    final_position_symbol: str | None = None
    final_position_quantity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int


class BacktestRunSummaryOut(BacktestRunSummaryIn):
    run_id: str
    persisted_at: datetime
