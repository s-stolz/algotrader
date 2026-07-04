from datetime import datetime
from typing import Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class BacktestContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BacktestStrategyPayload(BacktestContractModel):
    strategy_id: str
    parameters: dict[str, Any]


class BacktestExecutionPayload(BacktestContractModel):
    signal_timing: Literal["close"]
    fill_timing: Literal["next_open"]
    price_source: Literal["open", "close"]
    allow_partial_fills: bool
    allow_short: bool
    trade_accounting_policy: Literal["average_cost"]
    gap_policy: Literal["expire", "skip", "error"]
    intrabar_exit_policy: Literal[
        "conservative",
        "stop_first",
        "take_profit_first",
        "error",
    ]
    commission_bps: float
    slippage_bps: float


class BacktestRequestPayload(BacktestContractModel):
    symbols: list[str]
    exchange: str | None
    timeframe: str
    start_ms: int
    end_ms: int
    engine: Literal["vectorized", "event_driven"]
    data_granularity: Literal["bar", "tick"]
    initial_capital: float
    strategy: BacktestStrategyPayload
    execution: BacktestExecutionPayload
    persist_result: bool
    run_metadata: dict[str, Any] | None


class BacktestFillIn(BacktestContractModel):
    fill_sequence: int
    timestamp_ms: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fees: float
    exit_reason: Literal["signal", "stop_loss", "take_profit"] | None = None


class BacktestFillOut(BacktestFillIn):
    run_id: str


class BacktestClosedTradeIn(BacktestContractModel):
    trade_sequence: int
    trade_id: str
    symbol: str
    quantity: float
    entry_timestamp_ms: int
    entry_price: float
    exit_timestamp_ms: int
    exit_price: float
    realized_pnl: float
    fees: float
    exit_reason: Literal["signal", "stop_loss", "take_profit"]
    stop_loss_price: float | None = None
    take_profit_price: float | None = None


class BacktestClosedTradeOut(BacktestClosedTradeIn):
    run_id: str


class BacktestRunBase(BacktestContractModel):
    run_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_schema_version: int
    request: BacktestRequestPayload
    result_schema_version: int | None = None
    metrics: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None

    @field_validator("request_schema_version")
    @classmethod
    def validate_request_schema_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("request_schema_version must be 1")
        return value

    @field_validator("result_schema_version")
    @classmethod
    def validate_result_schema_version(cls, value: int | None) -> int | None:
        if value is not None and value not in (1, 2):
            raise ValueError("result_schema_version must be 1 or 2 when present")
        return value


class BacktestRunCreateIn(BacktestRunBase):
    fills: list[BacktestFillIn] = Field(default_factory=list)
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)


class BacktestRunOut(BacktestRunBase):
    pass


class BacktestRunConditionalUpdateIn(BacktestContractModel):
    expected_status: Literal["queued", "running", "succeeded", "failed"]
    new_status: Literal["queued", "running", "succeeded", "failed"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class BacktestRunCompleteIn(BacktestContractModel):
    expected_status: Literal["queued", "running", "succeeded", "failed"]
    completed_at: datetime
    result_schema_version: int
    metrics: dict[str, Any]
    diagnostics: dict[str, Any]
    fills: list[BacktestFillIn] = Field(default_factory=list)
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)

    @field_validator("result_schema_version")
    @classmethod
    def validate_result_schema_version(cls, value: int) -> int:
        if value not in (1, 2):
            raise ValueError("result_schema_version must be 1 or 2")
        return value


class BacktestRunMutationOut(BacktestContractModel):
    updated: bool
