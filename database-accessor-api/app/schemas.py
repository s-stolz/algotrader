import math
from datetime import datetime
from typing import Any, List, Literal, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictInt,
    field_validator,
    model_serializer,
    model_validator,
)


def validate_profit_factor(metrics: Mapping[str, Any]) -> None:
    """Require the saved JSON union without coercing missing or invalid values."""
    if "profit_factor" not in metrics:
        raise ValueError("metrics.profit_factor is required")
    value = metrics["profit_factor"]
    if value is None or value == "infinity":
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "metrics.profit_factor must be a nonnegative finite number, infinity, or null"
        )
    if not math.isfinite(value) or value < 0:
        raise ValueError(
            "metrics.profit_factor must be a nonnegative finite number, infinity, or null"
        )


class MarketIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    symbol: str = Field(min_length=1, max_length=128)
    exchange: str = Field(min_length=1, max_length=128)
    market_type: str = Field(min_length=1, max_length=20)
    min_move: float = Field(gt=0)
    settlement_currency: str = Field(min_length=1, max_length=12)
    contract_multiplier: float = Field(gt=0)
    minimum_quantity: float = Field(gt=0)
    quantity_step: float = Field(gt=0)
    source_type: Literal["custom", "broker"] = "custom"
    broker_provider: Literal["ctrader"] | None = None
    broker_account_id: str | None = Field(default=None, min_length=1, max_length=128)
    broker_environment: Literal["demo", "live"] | None = None
    broker_symbol_id: StrictInt | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_source(self) -> "MarketIn":
        binding = (
            self.broker_provider,
            self.broker_account_id,
            self.broker_environment,
            self.broker_symbol_id,
        )
        if self.source_type == "broker" and any(value is None for value in binding):
            raise ValueError("Broker markets require a complete broker instrument binding")
        if self.source_type == "custom" and any(value is not None for value in binding):
            raise ValueError("Custom markets cannot have a broker binding")
        return self

    @field_validator("symbol", "exchange", "settlement_currency", mode="before")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Identifiers must be strings")
        return value.strip().upper()

    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid IANA timezone: {value}") from exc
        return value


class CandleIn(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleBatchIn(BaseModel):
    market_id: StrictInt | None = Field(default=None, gt=0)
    symbol: str
    exchange: str | None = None
    candles: List[CandleIn]


class BacktestContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BacktestStrategyPayload(BacktestContractModel):
    strategy_id: str
    strategy_version: StrictInt | None = Field(default=None, gt=0)
    parameters: dict[str, Any]

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.strategy_version is None:
            payload.pop("strategy_version", None)
        return payload


class BacktestDailySchedulePayload(BacktestContractModel):
    entry_start_minute_utc: StrictInt = Field(ge=0, lt=1440)
    last_entry_minute_utc: StrictInt = Field(ge=0, lt=1440)
    exit_minute_utc: StrictInt = Field(ge=0, lt=1440)

    @model_validator(mode="after")
    def validate_boundaries(self) -> "BacktestDailySchedulePayload":
        if not self.entry_start_minute_utc < self.last_entry_minute_utc <= self.exit_minute_utc:
            raise ValueError("daily schedule requires entry start < last entry <= exit")
        return self


class SizingSchema(BacktestContractModel):
    mode: Literal["strategy", "units", "exposure", "equity_exposure", "risk", "equity_risk"] = (
        "strategy"
    )
    value: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    leverage: float = Field(default=1, ge=1, allow_inf_nan=False)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload = handler(self)
        if self.value is None:
            payload.pop("value", None)
        return payload


class ProtectionSchema(BacktestContractModel):
    mode: Literal["none", "strategy", "percent", "distance", "ticks"] = "strategy"
    value: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload = handler(self)
        if self.value is None:
            payload.pop("value", None)
        return payload


class InstrumentSchema(BacktestContractModel):
    symbol_id: StrictInt = Field(gt=0)
    settlement_currency: str = Field(min_length=1)
    contract_multiplier: float = Field(gt=0, allow_inf_nan=False)
    minimum_quantity: float = Field(gt=0, allow_inf_nan=False)
    quantity_step: float = Field(gt=0, allow_inf_nan=False)
    min_move: float = Field(gt=0, allow_inf_nan=False)


class BacktestExecutionPayload(BacktestContractModel):
    sizing: SizingSchema | None = None
    stop_loss: ProtectionSchema | None = None
    take_profit: ProtectionSchema | None = None
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
    daily_schedule: BacktestDailySchedulePayload | None = None
    max_entries_per_day: StrictInt | None = Field(default=None, gt=0)
    execution_mode: Literal["targets", "orders"] | None = None
    candle_quote: Literal["bid", "ask", "mid"] | None = None
    spread: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_position_quantity: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    intrabar_execution_policy: Literal["conservative", "optimistic", "error"] | None = None

    @model_validator(mode="after")
    def require_order_quote(self) -> "BacktestExecutionPayload":
        if self.execution_mode == "orders" and self.candle_quote is None:
            raise ValueError("Order execution requires an explicit candle_quote")
        return self

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        for field in (
            "sizing",
            "stop_loss",
            "take_profit",
            "daily_schedule",
            "max_entries_per_day",
            "execution_mode",
            "candle_quote",
            "spread",
            "max_position_quantity",
            "intrabar_execution_policy",
        ):
            if getattr(self, field) is None:
                payload.pop(field, None)
        return payload


class BacktestRequestPayload(BacktestContractModel):
    instrument: InstrumentSchema | None = None
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
    run_metadata: dict[str, Any] | None

    market_min_move: float | None = Field(default=None, gt=0, allow_inf_nan=False, strict=True)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.instrument is None:
            payload.pop("instrument", None)
        if self.market_min_move is None:
            payload.pop("market_min_move", None)
        return payload

    @field_validator("run_metadata")
    @classmethod
    def reject_metadata_names(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and ("name" in value or "label" in value):
            raise ValueError("Use the top-level experiment name instead of metadata name/label")
        return value


class BacktestFillIn(BacktestContractModel):
    fill_sequence: int
    timestamp_ms: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fees: float
    exit_reason: Literal["signal", "stop_loss", "take_profit", "account_depleted"] | None = None


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
    exit_reason: Literal["signal", "stop_loss", "take_profit", "account_depleted"]
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


class ExperimentNameModel(BacktestContractModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        if any(character in value for character in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"):
            raise ValueError("Experiment name must be single-line")
        name = value.strip()
        if len(name) > 120:
            raise ValueError("Experiment name must have at most 120 characters")
        return name or None


class ExperimentNameUpdateIn(BacktestContractModel):
    name: str | None

    _normalize_name = field_validator("name")(ExperimentNameModel.normalize_name.__func__)


class BacktestRunBase(BacktestContractModel):
    run_id: str
    backtest_id: str
    run_ordinal: int = Field(ge=0)
    status: Literal["queued", "running", "cancelling", "succeeded", "failed", "cancelled"]
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    cancellation_source: str | None = None
    cancellation_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_schema_version: int
    request: BacktestRequestPayload
    result_schema_version: int | None = None
    metrics: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    replay_descriptor: EquityReplayDescriptor | None = None

    @model_validator(mode="after")
    def validate_saved_metrics(self) -> "BacktestRunBase":
        if self.metrics is not None:
            validate_profit_factor(self.metrics)
        elif self.status == "succeeded":
            raise ValueError("successful Run requires metrics.profit_factor")
        return self

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
        if self.status in {"cancelling", "cancelled"} and (
            self.cancel_requested_at is None
            or not self.cancellation_source
            or not self.cancellation_reason
        ):
            raise ValueError("cancelled runs require cancellation provenance")
        return self


class BacktestRunOut(BacktestRunBase):
    pass


class BacktestRunMutationOut(BacktestContractModel):
    updated: bool


class BacktestExecutionClaimIn(BacktestContractModel):
    worker_id: str = Field(min_length=1)
    run_id: str
    owner_token: str
    started_at: datetime


class BacktestExecutionSettleIn(BacktestContractModel):
    run_id: str
    owner_token: str
    status: Literal["succeeded", "failed", "cancelled"]
    completed_at: datetime
    error_code: str | None = None
    error_message: str | None = None
    result_schema_version: int | None = None
    metrics: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    replay_descriptor: EquityReplayDescriptor | None = None
    fills: list[BacktestFillIn] = Field(default_factory=list)
    trades: list[BacktestClosedTradeIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_terminal(self) -> "BacktestExecutionSettleIn":
        if self.status == "succeeded":
            if self.result_schema_version != 3 or self.metrics is None or self.diagnostics is None:
                raise ValueError("successful settlement requires schema version 3 and results")
            validate_profit_factor(self.metrics)
            ending_equity = self.metrics.get("ending_equity")
            if (
                isinstance(ending_equity, bool)
                or not isinstance(ending_equity, (int, float))
                or not math.isfinite(ending_equity)
            ):
                raise ValueError("successful settlement requires finite metrics.ending_equity")
            if self.replay_descriptor is None:
                raise ValueError("successful settlement requires replay_descriptor")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("successful settlement cannot carry an error")
        elif self.status == "cancelled":
            if (
                self.error_code is not None
                or self.error_message is not None
                or self.fills
                or self.trades
                or self.result_schema_version is not None
                or self.metrics is not None
                or self.diagnostics is not None
                or self.replay_descriptor is not None
            ):
                raise ValueError("cancelled settlement cannot carry result artifacts")
        elif (
            not self.error_code
            or not self.error_message
            or self.fills
            or self.trades
            or self.result_schema_version is not None
            or self.metrics is not None
            or self.diagnostics is not None
            or self.replay_descriptor is not None
        ):
            raise ValueError("failed settlement requires an error and no results")
        return self


class BacktestExecutionReconcileIn(BacktestContractModel):
    completed_at: datetime
    error_code: str
    error_message: str


class BacktestExecutionFaultIn(BacktestContractModel):
    run_id: str
    owner_token: str
    code: str
    message: str


class BacktestExecutionSlotOut(BacktestContractModel):
    owner_token: str | None
    run_id: str | None
    fault_code: str | None
    fault_message: str | None


class BacktestExecutionReconcileOut(BacktestContractModel):
    reconciled: int | None


class BacktestWorkerHeartbeatIn(BacktestContractModel):
    worker_id: str
    owner_token: str | None = None
    fault_code: str | None = None
    fault_message: str | None = None


class BacktestWorkerHeartbeatOut(BacktestContractModel):
    worker_id: str
    owner_token: str | None
    heartbeat_at: datetime
    fault_code: str | None
    fault_message: str | None


class BacktestQueueStateOut(BacktestContractModel):
    snapshot_at: datetime
    slot: BacktestExecutionSlotOut
    active_run: dict[str, Any] | None
    heartbeats: list[BacktestWorkerHeartbeatOut]
    queued_entries: list[dict[str, Any]]


class BacktestMemberIn(BacktestContractModel):
    run_id: str
    run_ordinal: int = Field(ge=0)
    request_schema_version: Literal[3]
    request: BacktestRequestPayload


class BacktestCreateIn(ExperimentNameModel):
    backtest_id: str
    submission_id: str
    accepted_at: datetime
    definition_schema_version: Literal[1]
    accepted_definition: dict[str, Any]
    strategy_metadata: dict[str, Any]
    raw_count: int = Field(gt=0)
    member_count: int = Field(gt=0)
    excluded_count: int = Field(ge=0)
    members: list[BacktestMemberIn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_members(self) -> "BacktestCreateIn":
        shared = self.accepted_definition.get("shared_request", {})
        metadata = shared.get("run_metadata") if isinstance(shared, dict) else None
        if isinstance(metadata, dict) and ("name" in metadata or "label" in metadata):
            raise ValueError("Use the top-level experiment name instead of metadata name/label")
        if (
            self.member_count != len(self.members)
            or self.raw_count != self.member_count + self.excluded_count
        ):
            raise ValueError("Backtest counts do not match membership")
        if sorted(member.run_ordinal for member in self.members) != list(range(self.member_count)):
            raise ValueError("Backtest ordinals must be contiguous")
        if len({member.run_id for member in self.members}) != self.member_count:
            raise ValueError("Backtest member run IDs must be unique")
        if any(
            len(member.request.symbols) != 1
            or not member.request.symbols[0]
            or not member.request.timeframe
            or not member.request.exchange
            or member.request.strategy.strategy_version is None
            for member in self.members
        ):
            raise ValueError(
                "Backtest members require one resolved Market, Timeframe, and Strategy Version"
            )
        return self


class BacktestOut(ExperimentNameModel):
    backtest_id: str
    submission_id: str
    status: Literal[
        "queued", "running", "pausing", "paused", "cancelling", "completed", "cancelled"
    ]
    accepted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    cancellation_source: str | None = None
    cancellation_reason: str | None = None
    lifecycle_revision: int
    definition_schema_version: Literal[1]
    accepted_definition: dict[str, Any]
    strategy_metadata: dict[str, Any]
    raw_count: int
    member_count: int
    excluded_count: int


class BacktestEventOut(BacktestContractModel):
    backtest_id: str
    revision: int
    event_type: str
    prior_status: str | None = None
    status: str
    occurred_at: datetime
    reason: str | None = None
    trigger_run_id: str | None = None
    command_id: str | None = None


BacktestControlStatus = Literal[
    "queued", "running", "pausing", "paused", "cancelling", "completed", "cancelled"
]


class BacktestControlPolicyIn(BacktestContractModel):
    accepted_statuses: list[BacktestControlStatus] = Field(min_length=1)
    effective_statuses: list[BacktestControlStatus] = Field(min_length=1)
    active_status: BacktestControlStatus
    idle_status: BacktestControlStatus
    queue_action: Literal["remove", "append"]


class BacktestCommandIn(BacktestContractModel):
    command_id: str = Field(min_length=1, max_length=36)
    policy: BacktestControlPolicyIn


class BacktestCommandOut(BacktestContractModel):
    backtest_id: str
    status: str
    lifecycle_revision: int
    command_id: str | None = None


class HistoricalCandleBatchIn(CandleBatchIn):
    start_ms: int
    end_ms: int

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_ms > self.end_ms:
            raise ValueError("Historical interval must have start_ms <= end_ms")
        for candle in self.candles:
            if not self.start_ms <= candle.timestamp_ms <= self.end_ms:
                raise ValueError("Historical Candle lies outside the requested interval")
            if candle.timestamp_ms % 60000:
                raise ValueError("Historical M1 timestamps must be minute aligned")
        return self


class RecoverySource(BaseModel):
    symbol_id: int
    account_id: str

    @field_validator("account_id")
    @classmethod
    def validate_account(cls, value: str) -> str:
        if not value or len(value) > 128:
            raise ValueError("account_id must contain 1 to 128 characters")
        return value


class RecoveryBegin(RecoverySource):
    start_ms: int
    target_ms: int
    trigger: str

    @model_validator(mode="after")
    def validate_recovery(self):
        if self.start_ms < 0 or self.target_ms < self.start_ms - 1:
            raise ValueError("Recovery requires 0 <= start_ms <= target_ms + 1")
        if not self.trigger or len(self.trigger) > 64:
            raise ValueError("trigger must contain 1 to 64 characters")
        return self


class RecoveryAdvance(RecoverySource):
    recovery_id: str
    revision: int
    expected_start_ms: int
    next_ms: int

    @model_validator(mode="after")
    def validate_progress(self):
        if self.revision < 1 or not 0 <= self.expected_start_ms <= self.next_ms:
            raise ValueError("Recovery progress must advance the expected start")
        return self


class LiveWriteBegin(RecoverySource):
    boundary_ms: int = Field(ge=0)


class LiveWriteFinish(RecoverySource):
    write_id: str = Field(min_length=1, max_length=36)
