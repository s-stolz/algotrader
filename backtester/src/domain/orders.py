"""Persistent order commands emitted at completed strategy-candle boundaries."""

import math
from dataclasses import dataclass, field, replace
from enum import Enum

from domain.enums import OrderSide


class OrderAction(str, Enum):
    SUBMIT = "submit"
    UPDATE = "update"
    CANCEL = "cancel"
    PROTECT = "protect"


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
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    stop_loss_distance: float | None = None
    take_profit_distance: float | None = None
    stop_loss_ticks: int | None = None
    take_profit_ticks: int | None = None

    def __post_init__(self) -> None:  # noqa: C901
        for name, ticks, modes in (
            (
                "stop_loss_ticks",
                self.stop_loss_ticks,
                (self.stop_price, self.stop_loss_pct, self.stop_loss_distance),
            ),
            (
                "take_profit_ticks",
                self.take_profit_ticks,
                (self.take_profit_pct, self.take_profit_distance, self.take_profits or None),
            ),
        ):
            if ticks is not None:
                if type(ticks) is not int or ticks <= 0:
                    raise ValueError(f"{name} must be a positive integer")
                if any(mode is not None for mode in modes):
                    raise ValueError("Use tick protection or price/percentage protection, not both")
        if self.stop_price is not None:
            _positive("stop price", self.stop_price)
        object.__setattr__(self, "take_profits", tuple(self.take_profits))
        for value in (self.stop_loss_distance, self.take_profit_distance):
            if value is not None:
                _positive("protective distance", value)
        if self.stop_loss_distance is not None and (
            self.stop_price is not None or self.stop_loss_pct is not None
        ):
            raise ValueError("Use only one stop protection mode")
        if self.take_profit_distance is not None and (
            self.take_profits or self.take_profit_pct is not None
        ):
            raise ValueError("Use only one target protection mode")
        for value in (self.stop_loss_pct, self.take_profit_pct):
            if value is not None:
                _positive("protective percentage", value)
        if self.stop_loss_pct is not None and self.stop_loss_pct >= 100:
            raise ValueError("stop_loss_pct must be less than 100")
        if self.stop_price is not None and self.stop_loss_pct is not None:
            raise ValueError("Use a fixed stop or an average-entry percentage")
        if self.take_profits and self.take_profit_pct is not None:
            raise ValueError("Use fixed profit tiers or an average-entry percentage")

    def resolve_ticks(self, min_move: float | None) -> "OrderProtection":
        if self.stop_loss_ticks is None and self.take_profit_ticks is None:
            return self
        if (
            min_move is None
            or isinstance(min_move, bool)
            or not math.isfinite(min_move)
            or min_move <= 0
        ):
            raise ValueError("Market min_move is required for tick protection")
        return replace(
            self,
            stop_loss_distance=(
                self.stop_loss_ticks * min_move
                if self.stop_loss_ticks is not None
                else self.stop_loss_distance
            ),
            take_profit_distance=(
                self.take_profit_ticks * min_move
                if self.take_profit_ticks is not None
                else self.take_profit_distance
            ),
            stop_loss_ticks=None,
            take_profit_ticks=None,
        )


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
    only_when_flat: bool = False
    replace_group: str | None = None
    lifetime_bars: int | None = None
    price_offset_ticks: int = 0
    market: bool = False
    planned_risk: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("order_id must be non-empty")
        object.__setattr__(self, "side", OrderSide(self.side))
        if type(self.price_offset_ticks) is not int or self.price_offset_ticks < 0:
            raise ValueError("price_offset_ticks must be a nonnegative integer")
        _positive("limit price", self.price)
        _positive("order quantity", self.quantity)
        if self.expires_at_ms is not None and (
            type(self.expires_at_ms) is not int or self.expires_at_ms % 60_000
        ):
            raise ValueError("expiry must be an integer minute boundary")
        if self.lifetime_bars is not None:
            if type(self.lifetime_bars) is not int or self.lifetime_bars < 1:
                raise ValueError("lifetime_bars must be a positive integer")
            if self.expires_at_ms is not None:
                raise ValueError("Use an absolute expiry or lifetime_bars")
        if self.replace_group is not None and not self.replace_group.strip():
            raise ValueError("replace_group must be non-empty")
        if self.oco_group is not None and not self.oco_group.strip():
            raise ValueError("oco_group must be non-empty")

    def resolve_ticks(self, min_move: float | None) -> "LimitOrder":
        price = self.price
        if self.price_offset_ticks:
            if (
                min_move is None
                or isinstance(min_move, bool)
                or not math.isfinite(min_move)
                or min_move <= 0
            ):
                raise ValueError("Market min_move is required for a limit offset")
            distance = self.price_offset_ticks * min_move
            price += -distance if self.side == OrderSide.BUY else distance
        return replace(
            self,
            price=price,
            price_offset_ticks=0,
            protection=(
                self.protection.resolve_ticks(min_move) if self.protection is not None else None
            ),
        )


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
    protection: OrderProtection | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", OrderAction(self.action))
        if type(self.effective_at_ms) is not int or self.effective_at_ms % 60_000:
            raise ValueError("commands must take effect on minute boundaries")
        if not self.order_id.strip():
            raise ValueError("order_id must be non-empty")
        if self.action == OrderAction.PROTECT:
            if self.order is not None or self.protection is None:
                raise ValueError("protect requires protection and no entry order")
            return
        if self.protection is not None:
            raise ValueError("Only protect commands carry position protection")
        if self.action == OrderAction.CANCEL:
            if self.order is not None:
                raise ValueError("cancel must not carry an order")
        elif self.order is None or self.order.order_id != self.order_id:
            raise ValueError("submit/update requires an order with matching ID")


def _positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
