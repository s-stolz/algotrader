"""FastAPI request and response schemas for durable backtest runs."""

from __future__ import annotations

from typing import Any, Literal

from domain.enums import (
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
    BacktestRequest,
    BacktestRunRecord,
    ExecutionConfig,
    StrategyConfig,
)
from pydantic import BaseModel, ConfigDict, Field


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
    allow_short: bool = False
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
    start_ms: int
    end_ms: int
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
                allow_short=execution.allow_short,
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
    if not value:
        return "backtest_failed"
    return value[:100]


def _public_error_message(error_message: str | None) -> str:
    value = (error_message or "").strip()
    if not value:
        return "Backtest execution failed"
    if "\n" in value or "traceback" in value.lower():
        return "Backtest execution failed"
    return value[:500]
