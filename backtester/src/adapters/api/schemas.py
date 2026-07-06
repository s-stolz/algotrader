"""FastAPI request and response schemas for durable backtest runs."""

from __future__ import annotations

import re
from typing import Any, Literal

from domain.enums import (
    AllowedDirections,
    BacktestEngine,
    DataGranularity,
    FillTiming,
    GapPolicy,
    IntrabarExitPolicy,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRunRecord,
    BacktestTradeRecord,
    ExecutionConfig,
    StrategyConfig,
)
from pydantic import BaseModel, ConfigDict, Field, StrictInt

_PUBLIC_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,100}$")
_EXCEPTION_DETAIL_PATTERN = re.compile(r"(?:^|\s)[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):")


class ApiContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StrategyRequestSchema(ApiContractModel):
    strategy_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExecutionRequestSchema(ApiContractModel):
    signal_timing: Literal["close"] = "close"
    fill_timing: Literal["next_open"] = "next_open"
    price_source: Literal["open", "close"] = "open"
    allow_partial_fills: bool = False
    allowed_directions: Literal["long_only", "short_only", "long_and_short"] = "long_and_short"
    trade_accounting_policy: Literal["average_cost"] = "average_cost"
    gap_policy: Literal["expire", "skip", "error"] = "skip"
    intrabar_exit_policy: Literal[
        "conservative",
        "stop_first",
        "take_profit_first",
        "error",
    ] = "conservative"
    commission_bps: float = Field(default=0.0, ge=0.0)
    slippage_bps: float = Field(default=0.0, ge=0.0)


class BacktestSubmissionRequestSchema(ApiContractModel):
    symbols: list[str]
    exchange: str | None = None
    timeframe: str
    start_ms: StrictInt
    end_ms: StrictInt
    engine: Literal["vectorized", "event_driven"] = "vectorized"
    data_granularity: Literal["bar", "tick"] = "bar"
    initial_capital: float = Field(default=10_000.0, gt=0.0)
    strategy: StrategyRequestSchema
    execution: ExecutionRequestSchema = Field(default_factory=ExecutionRequestSchema)
    persist_result: bool = False
    run_metadata: dict[str, Any] | None = None

    def to_domain(self) -> BacktestRequest:
        execution = self.execution
        return BacktestRequest(
            symbols=list(self.symbols),
            exchange=self.exchange,
            timeframe=self.timeframe,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            engine=BacktestEngine(self.engine),
            data_granularity=DataGranularity(self.data_granularity),
            initial_capital=self.initial_capital,
            strategy=StrategyConfig(
                strategy_id=self.strategy.strategy_id,
                parameters=dict(self.strategy.parameters),
            ),
            execution=ExecutionConfig(
                signal_timing=SignalTiming(execution.signal_timing),
                fill_timing=FillTiming(execution.fill_timing),
                price_source=PriceSource(execution.price_source),
                allow_partial_fills=execution.allow_partial_fills,
                allowed_directions=AllowedDirections(execution.allowed_directions),
                trade_accounting_policy=TradeAccountingPolicy(execution.trade_accounting_policy),
                gap_policy=GapPolicy(execution.gap_policy),
                intrabar_exit_policy=IntrabarExitPolicy(execution.intrabar_exit_policy),
                commission_bps=execution.commission_bps,
                slippage_bps=execution.slippage_bps,
            ),
            persist_result=self.persist_result,
            run_metadata=(dict(self.run_metadata) if self.run_metadata is not None else None),
        )


class BacktestSubmissionResponseSchema(ApiContractModel):
    run_id: str
    status: Literal["queued"]


class BacktestFillResponseSchema(ApiContractModel):
    sequence: int
    timestamp_ms: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fees: float
    exit_reason: Literal["signal", "stop_loss", "take_profit"] | None = None

    @classmethod
    def from_domain(cls, fill: BacktestFillRecord) -> "BacktestFillResponseSchema":
        return cls(
            sequence=fill.sequence,
            timestamp_ms=fill.timestamp_ms,
            symbol=fill.symbol,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price,
            fees=fill.fees,
            exit_reason=(fill.exit_reason.value if fill.exit_reason is not None else None),
        )


class BacktestTradeResponseSchema(ApiContractModel):
    sequence: int
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

    @classmethod
    def from_domain(cls, trade: BacktestTradeRecord) -> "BacktestTradeResponseSchema":
        return cls(
            sequence=trade.sequence,
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            trade_direction=trade.trade_direction.value,
            quantity=trade.quantity,
            entry_timestamp_ms=trade.entry_timestamp_ms,
            entry_price=trade.entry_price,
            exit_timestamp_ms=trade.exit_timestamp_ms,
            exit_price=trade.exit_price,
            realized_pnl=trade.realized_pnl,
            fees=trade.fees,
            exit_reason=trade.exit_reason.value,
            stop_loss_price=trade.stop_loss_price,
            take_profit_price=trade.take_profit_price,
        )


class BacktestRunResponseSchema(ApiContractModel):
    run_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    submitted_at_ms: int
    started_at_ms: int | None = None
    completed_at_ms: int | None = None
    request_schema_version: int
    request: BacktestSubmissionRequestSchema
    result_schema_version: int | None = None
    metrics: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def from_domain(cls, run: BacktestRunRecord) -> "BacktestRunResponseSchema":
        payload: dict[str, Any] = {
            "run_id": run.run_id,
            "status": run.status.value,
            "submitted_at_ms": run.submitted_at_ms,
            "request_schema_version": run.request_snapshot.schema_version,
            "request": dict(run.request_snapshot.payload),
        }

        if run.status.value in {"running", "succeeded", "failed"}:
            payload["started_at_ms"] = run.started_at_ms
        if run.status.value in {"succeeded", "failed"}:
            payload["completed_at_ms"] = run.completed_at_ms

        if run.status.value == "succeeded":
            if run.result_schema_version is None or run.metrics is None or run.diagnostics is None:
                raise ValueError("Succeeded backtest run is missing result artifacts")
            payload["result_schema_version"] = run.result_schema_version
            payload["metrics"] = dict(run.metrics)
            payload["diagnostics"] = dict(run.diagnostics)
        elif run.status.value == "failed":
            payload["error_code"] = _public_error_code(run.error_code)
            payload["error_message"] = _public_error_message(run.error_message)

        return cls.model_validate(payload)


def _public_error_code(error_code: str | None) -> str:
    value = (error_code or "").strip()
    if not _PUBLIC_ERROR_CODE_PATTERN.fullmatch(value):
        return "backtest_failed"
    return value


def _public_error_message(error_message: str | None) -> str:
    value = (error_message or "").strip()
    if not value:
        return "Backtest execution failed"
    if "\n" in value or "traceback" in value.lower() or _EXCEPTION_DETAIL_PATTERN.search(value):
        return "Backtest execution failed"
    return value[:500]
