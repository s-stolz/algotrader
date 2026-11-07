"""Minute-bar limit matching with persistent orders and explicit OHLC paths.

The two admissible paths are O-H-L-C and O-L-H-C. Policy selects the
lower/higher closing equity outcome for this minute only, with O-H-L-C
as a stable tie-breaker. This is a model, not reconstruction of tick history.
"""

import math
from dataclasses import dataclass, field, replace
from typing import Sequence

from domain.enums import AllowedDirections, ExitReason, GapPolicy, OrderSide
from domain.orders import IntrabarExecutionPolicy, LimitOrder, OrderAction, OrderCommand
from domain.types import Fill


@dataclass(frozen=True)
class OrderExecutionConfig:
    spread: float = 0.0
    candle_quote: str = "bid"
    slippage_bps: float = 0.0
    commission_bps: float = 0.0
    policy: IntrabarExecutionPolicy = IntrabarExecutionPolicy.CONSERVATIVE
    gap_policy: GapPolicy = GapPolicy.SKIP
    allowed_directions: AllowedDirections = AllowedDirections.LONG_AND_SHORT
    max_position_quantity: float | None = None

    def __post_init__(self) -> None:
        for name in ("spread", "slippage_bps", "commission_bps"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.candle_quote not in ("bid", "ask", "mid"):
            raise ValueError("candle_quote must be bid, ask, or mid")
        object.__setattr__(self, "policy", IntrabarExecutionPolicy(self.policy))
        object.__setattr__(self, "gap_policy", GapPolicy(self.gap_policy))
        object.__setattr__(self, "allowed_directions", AllowedDirections(self.allowed_directions))
        if self.max_position_quantity is not None and (
            not math.isfinite(self.max_position_quantity) or self.max_position_quantity <= 0
        ):
            raise ValueError("max_position_quantity must be positive and finite")

    def quote_offset(self, side: OrderSide) -> float:
        bid_offset = {"bid": 0.0, "ask": -self.spread, "mid": -self.spread / 2}[self.candle_quote]
        return bid_offset + (self.spread if side == OrderSide.BUY else 0.0)


@dataclass
class OrderExecutionState:
    active: dict[str, LimitOrder] = field(default_factory=dict)
    submitted_ids: set[str] = field(default_factory=set)
    position: float = 0.0
    cash: float = 0.0
    stop_price: float | None = None
    targets: list[tuple[float, float]] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    ambiguous_minutes: int = 0

    def command(self, command: OrderCommand) -> None:
        key = command.order_id
        if command.action == OrderAction.SUBMIT:
            if key in self.submitted_ids:
                raise ValueError(f"Order ID already submitted: {key}")
            assert command.order is not None
            self.submitted_ids.add(key)
            self.active[key] = command.order
        elif key not in self.active:
            self.record(command.effective_at_ms, key, "inactive_noop")
            return
        elif command.action == OrderAction.CANCEL:
            del self.active[key]
        else:
            assert command.order is not None
            self.active[key] = command.order
        self.record(command.effective_at_ms, key, command.action.value)

    def record(self, timestamp: int, order_id: str, outcome: str) -> None:
        self.events.append({"timestamp_ms": timestamp, "order_id": order_id, "outcome": outcome})


def execute_minute(
    state: OrderExecutionState,
    *,
    symbol: str,
    timestamp_ms: int,
    prices: Sequence[float],
    config: OrderExecutionConfig,
) -> OrderExecutionState:
    """Return the selected state after one minute, leaving input state untouched."""
    if len(prices) != 4:
        raise ValueError("prices must contain open, high, low, close")
    base = replace(
        state,
        active=dict(state.active),
        submitted_ids=state.submitted_ids,
        targets=list(state.targets),
        fills=[],
        events=[],
    )
    for key, order in list(base.active.items()):
        if order.expires_at_ms is not None and timestamp_ms >= order.expires_at_ms:
            del base.active[key]
            base.record(timestamp_ms, key, "expired")
    opening, high, low, closing = prices
    if (
        not all(math.isfinite(p) and p > 0 for p in prices)
        or not low <= min(opening, closing) <= max(opening, closing) <= high
    ):
        if config.gap_policy == GapPolicy.ERROR:
            raise ValueError(f"Invalid execution candle at {timestamp_ms}")
        if config.gap_policy == GapPolicy.EXPIRE:
            for key in base.active:
                base.record(timestamp_ms, key, "gap_expired")
            base.active.clear()
        base.record(timestamp_ms, "", "invalid_candle")
        base.fills = state.fills + base.fills
        base.events = state.events + base.events
        return base
    paths = [(opening, high, low, closing), (opening, low, high, closing)]
    outcomes = [
        _path(
            replace(
                base,
                active=dict(base.active),
                targets=list(base.targets),
                fills=[],
                events=list(base.events),
            ),
            path,
            symbol,
            timestamp_ms,
            config,
        )
        for path in paths
    ]
    left, right = outcomes
    different = (
        left.fills != right.fills
        or left.active != right.active
        or left.stop_price != right.stop_price
        or left.targets != right.targets
    )
    if different and config.policy == IntrabarExecutionPolicy.ERROR:
        raise ValueError(f"Ambiguous intrabar execution at {timestamp_ms}")
    score = [s.cash + s.position * closing for s in outcomes]
    choose_right = (
        score[1] > score[0]
        if config.policy == IntrabarExecutionPolicy.OPTIMISTIC
        else score[1] < score[0]
    )
    result = right if choose_right else left
    if different:
        result.ambiguous_minutes += 1
        result.record(timestamp_ms, "", "ambiguous")
    result.fills = state.fills + result.fills
    result.events = state.events + result.events
    return result


def _path(
    state: OrderExecutionState,
    path: Sequence[float],
    symbol: str,
    timestamp: int,
    config: OrderExecutionConfig,
) -> OrderExecutionState:
    current = path[0]
    _at_price(state, current, symbol, timestamp, config)
    for end in path[1:]:
        while current != end:
            levels = [
                order.price - config.quote_offset(order.side) for order in state.active.values()
            ]
            if state.position:
                side = OrderSide.SELL if state.position > 0 else OrderSide.BUY
                offset = config.quote_offset(side)
                levels.extend(price - offset for price, _ in state.targets)
                if state.stop_price is not None:
                    levels.append(state.stop_price - offset)
            crossed = [
                level
                for level in levels
                if (current < level <= end if end > current else end <= level < current)
            ]
            current = (min(crossed) if end > current else max(crossed)) if crossed else end
            _at_price(state, current, symbol, timestamp, config)
    return state


def _at_price(  # noqa: C901
    state: OrderExecutionState,
    price: float,
    symbol: str,
    timestamp: int,
    config: OrderExecutionConfig,
) -> None:
    _protect(state, price, symbol, timestamp, config)
    for key in list(state.active):
        order = state.active.get(key)
        if order is None:
            continue
        quote = price + config.quote_offset(order.side)
        touched = quote <= order.price if order.side == OrderSide.BUY else quote >= order.price
        if not touched:
            continue
        del state.active[key]
        direction = 1 if order.side == OrderSide.BUY else -1
        quantity = order.quantity
        if order.reduce_only:
            quantity = min(quantity, abs(state.position)) if state.position * direction < 0 else 0
        if not quantity:
            state.record(timestamp, key, "reduce_only_cancelled")
            continue
        new_position = state.position + direction * quantity
        invalid = (
            (config.allowed_directions == AllowedDirections.LONG_ONLY and new_position < 0)
            or (config.allowed_directions == AllowedDirections.SHORT_ONLY and new_position > 0)
            or (
                config.max_position_quantity is not None
                and abs(new_position) > config.max_position_quantity
                and abs(new_position) > abs(state.position)
            )
        )
        if invalid:
            state.record(timestamp, key, "constraint_cancelled")
            continue
        _fill(state, symbol, timestamp, order.side, quantity, quote, config, limit=order.price)
        state.record(timestamp, key, "filled")
        if order.oco_group is not None:
            for sibling, pending in list(state.active.items()):
                if pending.oco_group == order.oco_group:
                    del state.active[sibling]
                    state.record(timestamp, sibling, "oco_cancelled")
        if order.protection is not None and state.position:
            state.stop_price = order.protection.stop_price
            state.targets = [
                (
                    tier.price,
                    (
                        tier.quantity
                        if tier.quantity is not None
                        else abs(state.position) * (tier.fraction or 0.0)
                    ),
                )
                for tier in order.protection.take_profits
            ]
        _protect(state, price, symbol, timestamp, config)


def _protect(
    state: OrderExecutionState,
    price: float,
    symbol: str,
    timestamp: int,
    config: OrderExecutionConfig,
) -> None:
    if not state.position:
        return
    long = state.position > 0
    side = OrderSide.SELL if long else OrderSide.BUY
    quote = price + config.quote_offset(side)
    stopped = state.stop_price is not None and (
        quote <= state.stop_price if long else quote >= state.stop_price
    )
    if stopped:
        _fill(
            state,
            symbol,
            timestamp,
            side,
            abs(state.position),
            quote,
            config,
            reason=ExitReason.STOP_LOSS,
        )
        for key in state.active:
            state.record(timestamp, key, "stop_cancelled")
        state.active.clear()
        return
    for target in list(state.targets):
        level, quantity = target
        if state.position and (quote >= level if long else quote <= level):
            state.targets.remove(target)
            _fill(
                state,
                symbol,
                timestamp,
                side,
                min(quantity, abs(state.position)),
                quote,
                config,
                limit=level,
                reason=ExitReason.TAKE_PROFIT,
            )


def _fill(
    state: OrderExecutionState,
    symbol: str,
    timestamp: int,
    side: OrderSide,
    quantity: float,
    raw_price: float,
    config: OrderExecutionConfig,
    limit: float | None = None,
    reason: ExitReason | None = None,
) -> None:
    direction = 1 if side == OrderSide.BUY else -1
    price = raw_price * (1 + direction * config.slippage_bps / 10_000)
    if limit is not None:
        price = min(price, limit) if direction > 0 else max(price, limit)
    if price <= 0:
        raise ValueError("Execution costs produced a nonpositive fill price")
    fees = quantity * price * config.commission_bps / 10_000
    before = state.position
    state.position += direction * quantity
    state.cash -= direction * quantity * price + fees
    state.fills.append(
        Fill(
            timestamp,
            symbol,
            quantity,
            price,
            side,
            fees,
            reason,
            state.stop_price,
            state.targets[0][0] if state.targets else None,
        )
    )
    if before * state.position <= 0:
        state.stop_price = None
        state.targets.clear()
