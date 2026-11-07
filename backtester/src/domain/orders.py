"""Persistent order commands emitted at completed strategy-candle boundaries."""

import math
from dataclasses import dataclass, field
from enum import Enum

from domain.enums import OrderSide


class OrderAction(str, Enum):
    SUBMIT = "submit"
    UPDATE = "update"
    CANCEL = "cancel"


class IntrabarExecutionPolicy(str, Enum):
    CONSERVATIVE = "conservative"
    OPTIMISTIC = "optimistic"
    ERROR = "error"


@dataclass(frozen=True)
class TakeProfitTier:
    price: float
    quantity: float | None = None
    fraction: float | None = None

    def __post_init__(self) -> None:
        _positive("take-profit price", self.price)
        if (self.quantity is None) == (self.fraction is None):
            raise ValueError("Specify exactly one of quantity or fraction")
        if self.quantity is not None:
            _positive("take-profit quantity", self.quantity)
        if self.fraction is not None:
            _positive("take-profit fraction", self.fraction)
            if self.fraction > 1:
                raise ValueError("take-profit fraction must be <= 1")


@dataclass(frozen=True)
class OrderProtection:
    stop_price: float | None = None
    take_profits: tuple[TakeProfitTier, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.stop_price is not None:
            _positive("stop price", self.stop_price)
        object.__setattr__(self, "take_profits", tuple(self.take_profits))


@dataclass(frozen=True)
class LimitOrder:
    order_id: str
    side: OrderSide
    price: float
    quantity: float
    expires_at_ms: int | None = None
    oco_group: str | None = None
    reduce_only: bool = False
    protection: OrderProtection | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("order_id must be non-empty")
        object.__setattr__(self, "side", OrderSide(self.side))
        _positive("limit price", self.price)
        _positive("order quantity", self.quantity)
        if self.expires_at_ms is not None and (
            type(self.expires_at_ms) is not int or self.expires_at_ms % 60_000
        ):
            raise ValueError("expiry must be an integer minute boundary")
        if self.oco_group is not None and not self.oco_group.strip():
            raise ValueError("oco_group must be non-empty")


@dataclass(frozen=True)
class OrderCommand:
    """An effective boundary, not the opening timestamp of the decision candle.

    UPDATE carries a complete replacement specification with the same ID.
    Inactive updates and cancellations never create a new order.
    """

    effective_at_ms: int
    action: OrderAction
    order_id: str
    order: LimitOrder | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", OrderAction(self.action))
        if type(self.effective_at_ms) is not int or self.effective_at_ms % 60_000:
            raise ValueError("commands must take effect on minute boundaries")
        if not self.order_id.strip():
            raise ValueError("order_id must be non-empty")
        if self.action == OrderAction.CANCEL:
            if self.order is not None:
                raise ValueError("cancel must not carry an order")
        elif self.order is None or self.order.order_id != self.order_id:
            raise ValueError("submit/update requires an order with matching ID")


def _positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
