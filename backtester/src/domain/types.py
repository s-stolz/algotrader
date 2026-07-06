"""Shared domain dataclasses and value contracts for backtester flows."""

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from domain.enums import (
    AllowedDirections,
    BacktestEngine,
    BacktestRunStatus,
    DataGranularity,
    ExitReason,
    FillTiming,
    GapPolicy,
    IntrabarExitPolicy,
    OrderSide,
    PositionSide,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)

BACKTEST_REQUEST_SCHEMA_VERSION = 2
BACKTEST_RESULT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProtectiveExitSpec:
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    def __post_init__(self) -> None:
        if self.stop_loss_pct is not None:
            stop_loss_pct = float(self.stop_loss_pct)
            if not math.isfinite(stop_loss_pct) or stop_loss_pct <= 0.0 or stop_loss_pct >= 100.0:
                raise ValueError(
                    "stop_loss_pct must be finite and greater than 0 and less than 100"
                )

            object.__setattr__(self, "stop_loss_pct", stop_loss_pct)

        if self.take_profit_pct is not None:
            take_profit_pct = float(self.take_profit_pct)
            if not math.isfinite(take_profit_pct) or take_profit_pct <= 0.0:
                raise ValueError("take_profit_pct must be finite and greater than 0")

            object.__setattr__(self, "take_profit_pct", take_profit_pct)


@dataclass(frozen=True)
class ExecutionConfig:
    signal_timing: SignalTiming = SignalTiming.CLOSE
    fill_timing: FillTiming = FillTiming.NEXT_OPEN
    price_source: PriceSource = PriceSource.OPEN
    allow_partial_fills: bool = False
    allowed_directions: AllowedDirections = AllowedDirections.LONG_AND_SHORT
    trade_accounting_policy: TradeAccountingPolicy = TradeAccountingPolicy.AVERAGE_COST
    gap_policy: GapPolicy = GapPolicy.SKIP
    intrabar_exit_policy: IntrabarExitPolicy = IntrabarExitPolicy.CONSERVATIVE
    commission_bps: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        try:
            allowed_directions = AllowedDirections(self.allowed_directions)
        except ValueError as exc:
            valid_values = ", ".join(direction.value for direction in AllowedDirections)
            raise ValueError(f"allowed_directions must be one of: {valid_values}") from exc
        object.__setattr__(self, "allowed_directions", allowed_directions)

        try:
            intrabar_exit_policy = IntrabarExitPolicy(self.intrabar_exit_policy)
        except ValueError as exc:
            valid_values = ", ".join(policy.value for policy in IntrabarExitPolicy)
            raise ValueError(f"intrabar_exit_policy must be one of: {valid_values}") from exc
        object.__setattr__(self, "intrabar_exit_policy", intrabar_exit_policy)

        if not math.isfinite(self.commission_bps):
            raise ValueError("commission_bps must be finite")
        if self.commission_bps < 0.0:
            raise ValueError("commission_bps must be >= 0")
        if not math.isfinite(self.slippage_bps):
            raise ValueError("slippage_bps must be finite")
        if self.slippage_bps < 0.0:
            raise ValueError("slippage_bps must be >= 0")


@dataclass(frozen=True)
class BacktestRequest:
    symbols: Sequence[str]
    timeframe: str
    start_ms: int
    end_ms: int
    strategy: StrategyConfig
    execution: ExecutionConfig
    initial_capital: float
    exchange: Optional[str] = None
    data_granularity: DataGranularity = DataGranularity.BAR
    persist_result: bool = False
    run_metadata: Optional[Dict[str, Any]] = None
    engine: BacktestEngine = BacktestEngine.VECTORIZED


@dataclass(frozen=True)
class BacktestRequestSnapshot:
    schema_version: int
    payload: Mapping[str, Any]

    @classmethod
    def from_request(cls, request: BacktestRequest) -> "BacktestRequestSnapshot":
        return cls(
            schema_version=BACKTEST_REQUEST_SCHEMA_VERSION,
            payload=_backtest_request_payload(request),
        )

    def to_request(self) -> BacktestRequest:
        if self.schema_version != BACKTEST_REQUEST_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported backtest request schema version: " f"{self.schema_version}"
            )
        return _backtest_request_from_payload(self.payload)


@dataclass(frozen=True)
class BacktestRunRecord:
    run_id: str
    status: BacktestRunStatus
    submitted_at_ms: int
    request_snapshot: BacktestRequestSnapshot
    started_at_ms: Optional[int] = None
    completed_at_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result_schema_version: Optional[int] = None
    metrics: Optional[Mapping[str, Any]] = None
    diagnostics: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class BacktestFillRecord:
    run_id: str
    sequence: int
    timestamp_ms: int
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fees: float
    exit_reason: Optional[ExitReason] = None


@dataclass(frozen=True)
class BacktestTradeRecord:
    run_id: str
    sequence: int
    trade_id: str
    symbol: str
    quantity: float
    entry_timestamp_ms: int
    entry_price: float
    exit_timestamp_ms: int
    exit_price: float
    realized_pnl: float
    fees: float
    exit_reason: ExitReason
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass(frozen=True)
class BacktestRunQuery:
    status: Optional[BacktestRunStatus] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    strategy_id: Optional[str] = None
    engine: Optional[BacktestEngine] = None
    submitted_from_ms: Optional[int] = None
    submitted_to_ms: Optional[int] = None


@dataclass(frozen=True)
class BarView:
    timestamp_ms: int
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class TickView:
    timestamp_ms: int
    symbol: str
    bid: float
    ask: float
    last: float
    size: float


@dataclass(frozen=True)
class PositionView:
    symbol: str
    quantity: float
    average_price: float
    side: PositionSide


@dataclass(frozen=True)
class PortfolioView:
    cash: float
    equity: float
    positions: Mapping[str, PositionView] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureMatrix:
    timestamp_ms: Sequence[int]
    features_by_symbol: Mapping[str, Mapping[str, Sequence[float]]]


@dataclass(frozen=True)
class SignalMatrix:
    timestamp_ms: Sequence[int]
    signals_by_symbol: Mapping[str, Sequence[int]]


@dataclass(frozen=True)
class ExecutionArrayBundle:
    timestamp_ms: Sequence[int]
    target_quantity_by_symbol: Mapping[str, Sequence[float]]


@dataclass(frozen=True)
class Fill:
    timestamp_ms: int
    symbol: str
    quantity: float
    price: float
    side: OrderSide
    fees: float = 0.0
    exit_reason: Optional[ExitReason] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass(frozen=True)
class Trade:
    trade_id: str
    symbol: str
    quantity: float
    entry_timestamp_ms: int
    entry_price: float
    exit_timestamp_ms: Optional[int] = None
    exit_price: Optional[float] = None
    realized_pnl: float = 0.0
    fees: float = 0.0
    exit_reason: ExitReason = ExitReason.SIGNAL
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    timestamp_ms: int
    cash: float
    equity: float
    positions: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestResult:
    request: BacktestRequest
    fills: List[Fill] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[PortfolioSnapshot] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    backtest_run_id: Optional[str] = None
    persisted_at: Optional[int] = None


_REQUEST_PAYLOAD_FIELDS = {
    "symbols",
    "exchange",
    "timeframe",
    "start_ms",
    "end_ms",
    "engine",
    "data_granularity",
    "initial_capital",
    "strategy",
    "execution",
    "persist_result",
    "run_metadata",
}
_STRATEGY_PAYLOAD_FIELDS = {"strategy_id", "parameters"}
_EXECUTION_PAYLOAD_FIELDS = {
    "signal_timing",
    "fill_timing",
    "price_source",
    "allow_partial_fills",
    "allowed_directions",
    "trade_accounting_policy",
    "gap_policy",
    "intrabar_exit_policy",
    "commission_bps",
    "slippage_bps",
}


def _backtest_request_payload(request: BacktestRequest) -> Dict[str, Any]:
    execution = request.execution
    return {
        "symbols": [str(symbol) for symbol in request.symbols],
        "exchange": request.exchange,
        "timeframe": str(request.timeframe),
        "start_ms": int(request.start_ms),
        "end_ms": int(request.end_ms),
        "engine": _enum_value(request.engine),
        "data_granularity": _enum_value(request.data_granularity),
        "initial_capital": float(request.initial_capital),
        "strategy": {
            "strategy_id": str(request.strategy.strategy_id),
            "parameters": deepcopy(request.strategy.parameters),
        },
        "execution": {
            "signal_timing": _enum_value(execution.signal_timing),
            "fill_timing": _enum_value(execution.fill_timing),
            "price_source": _enum_value(execution.price_source),
            "allow_partial_fills": bool(execution.allow_partial_fills),
            "allowed_directions": _enum_value(execution.allowed_directions),
            "trade_accounting_policy": _enum_value(execution.trade_accounting_policy),
            "gap_policy": _enum_value(execution.gap_policy),
            "intrabar_exit_policy": _enum_value(execution.intrabar_exit_policy),
            "commission_bps": float(execution.commission_bps),
            "slippage_bps": float(execution.slippage_bps),
        },
        "persist_result": bool(request.persist_result),
        "run_metadata": deepcopy(request.run_metadata),
    }


def _backtest_request_from_payload(payload: Mapping[str, Any]) -> BacktestRequest:
    _validate_payload_fields("Backtest request", payload, _REQUEST_PAYLOAD_FIELDS)
    strategy = _mapping_field(payload, "strategy")
    execution = _mapping_field(payload, "execution")
    _validate_payload_fields("Backtest strategy", strategy, _STRATEGY_PAYLOAD_FIELDS)
    _validate_payload_fields("Backtest execution", execution, _EXECUTION_PAYLOAD_FIELDS)

    symbols = payload["symbols"]
    if not isinstance(symbols, (list, tuple)) or not all(
        isinstance(symbol, str) for symbol in symbols
    ):
        raise ValueError("Backtest request symbols must be a list of strings")

    exchange = payload["exchange"]
    if exchange is not None and not isinstance(exchange, str):
        raise ValueError("Backtest request exchange must be a string or null")

    parameters = strategy["parameters"]
    if not isinstance(parameters, Mapping):
        raise ValueError("Backtest strategy parameters must be an object")

    run_metadata = payload["run_metadata"]
    if run_metadata is not None and not isinstance(run_metadata, Mapping):
        raise ValueError("Backtest request run_metadata must be an object or null")

    return BacktestRequest(
        symbols=list(symbols),
        exchange=exchange,
        timeframe=str(payload["timeframe"]),
        start_ms=int(payload["start_ms"]),
        end_ms=int(payload["end_ms"]),
        strategy=StrategyConfig(
            strategy_id=str(strategy["strategy_id"]),
            parameters=deepcopy(dict(parameters)),
        ),
        execution=ExecutionConfig(
            signal_timing=SignalTiming(execution["signal_timing"]),
            fill_timing=FillTiming(execution["fill_timing"]),
            price_source=PriceSource(execution["price_source"]),
            allow_partial_fills=bool(execution["allow_partial_fills"]),
            allowed_directions=AllowedDirections(execution["allowed_directions"]),
            trade_accounting_policy=TradeAccountingPolicy(execution["trade_accounting_policy"]),
            gap_policy=GapPolicy(execution["gap_policy"]),
            intrabar_exit_policy=IntrabarExitPolicy(execution["intrabar_exit_policy"]),
            commission_bps=float(execution["commission_bps"]),
            slippage_bps=float(execution["slippage_bps"]),
        ),
        initial_capital=float(payload["initial_capital"]),
        data_granularity=DataGranularity(payload["data_granularity"]),
        persist_result=bool(payload["persist_result"]),
        run_metadata=deepcopy(dict(run_metadata)) if run_metadata is not None else None,
        engine=BacktestEngine(payload["engine"]),
    )


def _mapping_field(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"Backtest request {field_name} must be an object")
    return value


def _validate_payload_fields(
    name: str,
    payload: Mapping[str, Any],
    required_fields: set[str],
) -> None:
    actual_fields = set(payload)
    missing_fields = sorted(required_fields - actual_fields)
    if missing_fields:
        raise ValueError(f"{name} missing required fields: {', '.join(missing_fields)}")
    unknown_fields = sorted(actual_fields - required_fields)
    if unknown_fields:
        raise ValueError(f"{name} contains unknown fields: {', '.join(unknown_fields)}")


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))
