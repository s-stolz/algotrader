from datetime import datetime
from typing import Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
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
    strategy_version: StrictInt | None = Field(default=None, gt=0)
    parameters: dict[str, Any]


class BacktestExecutionPayload(BacktestContractModel):
    signal_timing: Literal["close"]
    fill_timing: Literal["next_open"]
    price_source: Literal["open", "close"]
    allow_partial_fills: bool
    allowed_directions: Literal["long_only", "short_only", "long_and_short"]
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
    trade_direction: Literal["long", "short"]
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


class EquityReplayDescriptor(BacktestContractModel):
    schema_version: Literal[1]
    fingerprint_algorithm: Literal["sha256-ts-close-v1"]
    fingerprint_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_point_count: int = Field(gt=0)
    first_timestamp_ms: int
    last_timestamp_ms: int

    @model_validator(mode="after")
    def validate_timestamps(self) -> "EquityReplayDescriptor":
        if self.last_timestamp_ms < self.first_timestamp_ms:
            raise ValueError("last_timestamp_ms precedes first_timestamp_ms")
        return self


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
    replay_descriptor: EquityReplayDescriptor | None = None

    @field_validator("request_schema_version")
    @classmethod
    def validate_request_schema_version(cls, value: int) -> int:
        if value not in (2, 3):
            raise ValueError("request_schema_version must be 2 or 3")
        return value

    @field_validator("result_schema_version")
    @classmethod
    def validate_result_schema_version(cls, value: int | None) -> int | None:
        if value is not None and value not in (1, 2, 3):
            raise ValueError("result_schema_version must be 1, 2, or 3 when present")
        return value

    @model_validator(mode="after")
    def validate_success_result_schema_version(self) -> "BacktestRunBase":
        if self.status == "succeeded" and self.result_schema_version not in (1, 2, 3):
            raise ValueError("succeeded backtest runs require a result_schema_version")
        if self.request_schema_version == 3 and (
            self.request.strategy.strategy_version is None
            or self.request.strategy.strategy_version <= 0
        ):
            raise ValueError("request schema version 3 requires a positive strategy_version")
        if self.request_schema_version == 2 and self.request.strategy.strategy_version is not None:
            raise ValueError("request schema version 2 has no strategy_version")
        return self


class BacktestRunCreateIn(BacktestRunBase):
    @model_validator(mode="after")
    def validate_new_success_descriptor(self) -> "BacktestRunCreateIn":
        if self.status == "succeeded" and self.replay_descriptor is None:
            raise ValueError("successful runs require replay_descriptor")
        return self

    fills: list[BacktestFillIn] = Field(default_factory=list)
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_current_result_schema(self) -> "BacktestRunCreateIn":
        if self.result_schema_version is not None and self.result_schema_version != 3:
            raise ValueError("new succeeded backtest runs must use result_schema_version 3")
        return self


class BacktestRunOut(BacktestRunBase):
    pass


class BacktestRunConditionalUpdateIn(BacktestContractModel):
    expected_status: Literal["queued", "running", "succeeded", "failed"]
    new_status: Literal["queued", "running", "succeeded", "failed"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    @field_validator("new_status")
    @classmethod
    def validate_new_status(cls, value: str) -> str:
        if value == "succeeded":
            raise ValueError("succeeded backtest runs must use the completion endpoint")
        return value


class BacktestRunCompleteIn(BacktestContractModel):
    expected_status: Literal["running"]
    completed_at: datetime
    result_schema_version: int
    metrics: dict[str, Any]
    diagnostics: dict[str, Any]
    replay_descriptor: EquityReplayDescriptor
    fills: list[BacktestFillIn] = Field(default_factory=list)
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)

    @field_validator("result_schema_version")
    @classmethod
    def validate_result_schema_version(cls, value: int) -> int:
        if value != 3:
            raise ValueError("result_schema_version must be 3")
        return value


class BacktestRunMutationOut(BacktestContractModel):
    updated: bool
