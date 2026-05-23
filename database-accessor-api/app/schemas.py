from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator
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


class BacktestClosedTradeIn(BaseModel):
    trade_id: str
    symbol: str
    quantity: float
    entry_timestamp_ms: int
    entry_price: float
    exit_timestamp_ms: int
    exit_price: float
    realized_pnl: float
    fees: float
    exit_reason: Literal["signal", "stop_loss", "take_profit"] = "signal"


class BacktestClosedTradeOut(BacktestClosedTradeIn):
    run_id: str


class BacktestRunSummaryBase(BaseModel):
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


class BacktestRunSummaryIn(BacktestRunSummaryBase):
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)


class BacktestRunSummaryOut(BacktestRunSummaryBase):
    run_id: str
    persisted_at: datetime
