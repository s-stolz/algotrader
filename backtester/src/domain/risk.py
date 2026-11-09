"""Linear instrument valuation, submission-time sizing, and margin policy.

Prices and quantities retain instrument units. All monetary values use the
instrument's settlement currency; no implicit currency conversion is performed.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

SizingMode = Literal["strategy", "units", "exposure", "equity_exposure", "risk", "equity_risk"]
ProtectionMode = Literal["none", "strategy", "percent", "distance", "ticks"]


def positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


@dataclass(frozen=True)
class InstrumentSpec:
    symbol_id: int
    settlement_currency: str
    contract_multiplier: float
    minimum_quantity: float
    quantity_step: float
    min_move: float

    def __post_init__(self) -> None:
        if type(self.symbol_id) is not int or self.symbol_id <= 0:
            raise ValueError("symbol_id must be a positive integer")
        if (
            not self.settlement_currency
            or self.settlement_currency != self.settlement_currency.strip().upper()
        ):
            raise ValueError("settlement_currency must be a nonempty uppercase currency code")
        for name in ("contract_multiplier", "minimum_quantity", "quantity_step", "min_move"):
            positive(name, getattr(self, name))

    def notional(self, quantity: float, price: float) -> float:
        return abs(quantity) * price * self.contract_multiplier

    def round_quantity(self, quantity: float) -> float:
        positive("quantity", quantity)
        step = Decimal(str(self.quantity_step))
        rounded = (Decimal(str(quantity)) / step).to_integral_value(rounding=ROUND_FLOOR) * step
        return float(rounded) if rounded >= Decimal(str(self.minimum_quantity)) else 0.0


@dataclass(frozen=True)
class ProtectionSetting:
    mode: ProtectionMode = "strategy"
    value: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("none", "strategy", "percent", "distance", "ticks"):
            raise ValueError("Unknown protection mode")
        if self.mode in ("none", "strategy"):
            if self.value is not None:
                raise ValueError("This protection mode does not accept a value")
        elif self.value is None:
            raise ValueError("Configured protection requires a value")
        else:
            positive("protection value", self.value)

    def level(
        self, entry: float, direction: int, instrument: InstrumentSpec, *, stop: bool
    ) -> float | None:
        if self.mode in ("none", "strategy"):
            return None
        assert self.value is not None
        distance = self.value
        if self.mode == "percent":
            distance *= entry / 100
        elif self.mode == "ticks":
            distance *= instrument.min_move
        return entry + direction * (-distance if stop else distance)


@dataclass(frozen=True)
class SizingPolicy:
    mode: SizingMode = "strategy"
    value: float | None = None
    leverage: float = 1.0

    def __post_init__(self) -> None:
        if self.mode not in (
            "strategy",
            "units",
            "exposure",
            "equity_exposure",
            "risk",
            "equity_risk",
        ):
            raise ValueError("Unknown sizing mode")
        positive("leverage", self.leverage)
        if self.leverage < 1:
            raise ValueError("leverage must be at least 1")
        if self.mode == "strategy":
            if self.value is not None:
                raise ValueError("Strategy sizing does not accept a shared value")
        elif self.value is None:
            raise ValueError("Sizing mode requires a value")
        else:
            positive("sizing value", self.value)


@dataclass(frozen=True)
class SizingDecision:
    mode: SizingMode
    equity: float
    requested_budget: float | None
    entry_price: float
    stop_price: float | None
    requested_quantity: float
    quantity: float
    planned_risk: float | None
    reason: str | None = None


def size_entry(  # noqa: C901
    policy: SizingPolicy,
    instrument: InstrumentSpec,
    *,
    equity: float,
    entry_price: float,
    direction: int,
    strategy_quantity: float,
    stop_price: float | None,
) -> SizingDecision:
    """Resolve one entry without future prices or execution-cost estimates."""
    positive("entry_price", entry_price)
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if not math.isfinite(equity):
        raise ValueError("equity must be finite")
    budget = policy.value
    quantity = 0.0
    reason = None
    distance = None
    if stop_price is not None and math.isfinite(stop_price) and stop_price > 0:
        candidate = direction * (entry_price - stop_price)
        if candidate > 0:
            distance = candidate * instrument.contract_multiplier
    if equity <= 0:
        reason = "account_depleted"
    elif policy.mode in ("risk", "equity_risk") and distance is None:
        reason = "invalid_stop"
    else:
        if policy.mode in ("equity_exposure", "equity_risk"):
            assert budget is not None
            budget *= equity / 100
        if policy.mode == "strategy":
            positive("strategy_quantity", strategy_quantity)
            quantity = strategy_quantity
        elif policy.mode == "units":
            assert budget is not None
            quantity = budget
        elif policy.mode in ("risk", "equity_risk"):
            assert budget is not None and distance is not None
            quantity = budget / distance
        else:
            assert budget is not None
            quantity = budget / instrument.notional(1, entry_price)
    rounded = instrument.round_quantity(quantity) if quantity > 0 else 0.0
    if reason is None and rounded == 0:
        reason = "below_minimum_quantity"
    return SizingDecision(
        policy.mode,
        equity,
        budget,
        entry_price,
        stop_price,
        quantity,
        rounded,
        rounded * distance if distance is not None else None,
        reason,
    )


def available_margin(
    instrument: InstrumentSpec,
    *,
    equity: float,
    position: float,
    price: float,
    leverage: float,
    reserved_margin: float = 0.0,
) -> float:
    positive("leverage", leverage)
    return equity - instrument.notional(position, price) / leverage - reserved_margin
