"""Shared domain dataclasses and value contracts for backtester flows."""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from domain.enums import (
    BacktestEngine,
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
    allow_short: bool = False
    trade_accounting_policy: TradeAccountingPolicy = TradeAccountingPolicy.AVERAGE_COST
    gap_policy: GapPolicy = GapPolicy.SKIP
    intrabar_exit_policy: IntrabarExitPolicy = IntrabarExitPolicy.CONSERVATIVE
    commission_bps: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
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
    data_granularity: DataGranularity = DataGranularity.BAR
    persist_result: bool = False
    run_metadata: Optional[Dict[str, Any]] = None
    engine: BacktestEngine = BacktestEngine.VECTORIZED


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
