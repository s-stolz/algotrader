"""Independent event-driven order matching with persistent orders.

The two admissible paths are O-H-L-C and O-L-H-C. Policy selects the
lower/higher closing equity outcome for this minute only, with O-H-L-C
as a stable tie-breaker. This is a model, not reconstruction of tick history.
"""

import math
from dataclasses import asdict, dataclass, field, replace
from typing import Sequence

from domain.enums import AllowedDirections, ExitReason, GapPolicy, OrderSide
from domain.orders import (
    IntrabarExecutionPolicy,
    LimitOrder,
    OrderAction,
    OrderCommand,
    OrderProtection,
)
from domain.risk import InstrumentSpec, ProtectionSetting, SizingPolicy, size_entry
from domain.schedule import DAY_MS, DailyTradingSchedule
from domain.types import Fill


@dataclass(frozen=True)
class EventOrderConfig:
    instrument: InstrumentSpec | None = None
    sizing: SizingPolicy | None = None
    stop_loss: ProtectionSetting | None = None
    take_profit: ProtectionSetting | None = None
    initial_capital: float = 0.0
    spread: float = 0.0
    candle_quote: str = "bid"
    slippage_bps: float = 0.0
    commission_bps: float = 0.0
    policy: IntrabarExecutionPolicy = IntrabarExecutionPolicy.CONSERVATIVE
    gap_policy: GapPolicy = GapPolicy.SKIP
    allowed_directions: AllowedDirections = AllowedDirections.LONG_AND_SHORT
    max_position_quantity: float | None = None
    daily_schedule: DailyTradingSchedule | None = None
    max_entries_per_day: int | None = None

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
class EventOrderState:
    config: EventOrderConfig | None = None
    last_price: float | None = None
    depleted: bool = False
    active: dict[str, LimitOrder] = field(default_factory=dict)
    submitted_ids: set[str] = field(default_factory=set)
    position: float = 0.0
    cash: float = 0.0
    stop_price: float | None = None
    targets: list[tuple[float, float]] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    ambiguous_minutes: int = 0
    average_entry: float = 0.0
    relative_stop: float | None = None
    relative_target: float | None = None
    entry_timestamp_ms: int | None = None
    entry_day: int | None = None
    entries_today: int = 0

    def command(self, command: OrderCommand) -> None:  # noqa: C901
        for identity, active in list(self.active.items()):
            if active.expires_at_ms is not None and active.expires_at_ms <= command.effective_at_ms:
                del self.active[identity]
                self.record(active.expires_at_ms, identity, "expired")
        if self.depleted:
            return
        key = command.order_id
        if command.action == OrderAction.PROTECT:
            if self.position:
                assert command.protection is not None
                protection = command.protection
                if self.config is not None:
                    if (
                        self.config.stop_loss is not None
                        and self.config.stop_loss.mode != "strategy"
                    ):
                        protection = replace(
                            protection,
                            stop_price=self.stop_price,
                            stop_loss_pct=None,
                            stop_loss_distance=None,
                        )
                    if (
                        self.config.take_profit is not None
                        and self.config.take_profit.mode != "strategy"
                    ):
                        from domain.orders import TakeProfitTier

                        protection = replace(
                            protection,
                            take_profits=tuple(
                                TakeProfitTier(level, quantity=quantity)
                                for level, quantity in self.targets
                            ),
                            take_profit_pct=None,
                            take_profit_distance=None,
                        )
                self.set_protection(protection, abs(self.position))
                self.record(command.effective_at_ms, key, "protection_updated")
            else:
                self.record(command.effective_at_ms, key, "inactive_noop")
            return
        if command.action == OrderAction.SUBMIT:
            if key in self.submitted_ids:
                raise ValueError(f"Order ID already submitted: {key}")
            assert command.order is not None
            self.submitted_ids.add(key)
            if command.order.only_when_flat and self.position:
                self.record(command.effective_at_ms, key, "position_open_ignored")
                return
            if command.order.replace_group is not None:
                for identity, pending in list(self.active.items()):
                    if pending.replace_group == command.order.replace_group:
                        del self.active[identity]
                        self.record(command.effective_at_ms, identity, "replaced")
            self.active[key] = command.order
        elif key not in self.active:
            self.record(command.effective_at_ms, key, "inactive_noop")
            return
        elif command.action == OrderAction.CANCEL:
            del self.active[key]
        else:
            assert command.order is not None
            self.active[key] = command.order
        if command.action != OrderAction.CANCEL and not self.prepare_order(
            key, command.effective_at_ms
        ):
            return
        self.record(command.effective_at_ms, key, command.action.value)

    def reserved_margin(self) -> float:
        config = self.config
        if config is None or config.instrument is None or config.sizing is None:
            return 0.0
        return sum(
            config.instrument.notional(
                max(
                    0.0,
                    order.quantity
                    - (
                        abs(self.position)
                        if self.position * (1 if order.side == OrderSide.BUY else -1) < 0
                        else 0.0
                    ),
                ),
                order.price,
            )
            / config.sizing.leverage
            for order in self.active.values()
            if not order.reduce_only
        )

    def prepare_order(self, key: str, timestamp: int) -> bool:  # noqa: C901
        config = self.config
        if config is None or config.instrument is None or config.sizing is None:
            return True
        order = self.active.pop(key)
        direction = 1 if order.side == OrderSide.BUY else -1
        if order.reduce_only or (
            self.position * direction < 0 and order.quantity <= abs(self.position)
        ):
            self.active[key] = order
            return True
        spec = config.instrument
        direction = 1 if order.side == OrderSide.BUY else -1
        mark = self.last_price if self.last_price is not None else order.price
        equity = (
            config.initial_capital + self.cash + self.position * mark * spec.contract_multiplier
        )
        protection = order.protection or OrderProtection()
        stop = protection.stop_price
        if protection.stop_loss_pct is not None:
            stop = order.price * (1 - direction * protection.stop_loss_pct / 100)
        if protection.stop_loss_distance is not None:
            stop = order.price - direction * protection.stop_loss_distance
        setting = config.stop_loss
        if setting is not None and setting.mode != "strategy":
            stop = (
                self.stop_price
                if self.position * direction > 0
                else setting.level(order.price, direction, spec, stop=True)
            )
        decision = size_entry(
            config.sizing,
            spec,
            equity=equity,
            entry_price=order.price,
            direction=direction,
            strategy_quantity=order.quantity
            - (abs(self.position) if self.position * direction < 0 else 0.0),
            stop_price=stop,
        )
        self.events.append(
            {"timestamp_ms": timestamp, "order_id": key, "outcome": "sizing", **asdict(decision)}
        )
        if decision.reason:
            self.record(timestamp, key, decision.reason)
            if self.position * direction < 0:
                self.active[key] = replace(
                    order, quantity=abs(self.position), reduce_only=True, protection=None
                )
                return True
            return False
        quantity = decision.quantity
        # Opposite orders close existing exposure before opening the sized entry.
        closing = abs(self.position) if self.position * direction < 0 else 0.0
        required = spec.notional(quantity, order.price) / config.sizing.leverage
        used = 0.0 if closing else spec.notional(self.position, mark) / config.sizing.leverage
        if required > equity - used - self.reserved_margin():
            self.record(timestamp, key, "insufficient_margin")
            if closing:
                self.active[key] = replace(
                    order, quantity=closing, reduce_only=True, protection=None
                )
                return True
            return False
        protection = replace(
            protection, stop_price=stop, stop_loss_pct=None, stop_loss_distance=None
        )
        target = config.take_profit
        if target is not None and target.mode != "strategy":
            from domain.orders import TakeProfitTier

            level = (
                self.targets[0][0]
                if self.position * direction > 0 and self.targets
                else target.level(order.price, direction, spec, stop=False)
            )
            protection = replace(
                protection,
                take_profit_pct=None,
                take_profit_distance=None,
                take_profits=(TakeProfitTier(level, fraction=1.0),) if level is not None else (),
            )
        self.active[key] = replace(
            order,
            quantity=quantity + closing,
            protection=protection,
            planned_risk=decision.planned_risk,
        )
        return True

    def set_protection(self, protection: OrderProtection, quantity: float) -> None:
        self.stop_price = protection.stop_price
        self.targets = [
            (
                tier.price,
                tier.quantity if tier.quantity is not None else quantity * (tier.fraction or 0.0),
            )
            for tier in protection.take_profits
        ]
        self.relative_stop = protection.stop_loss_pct
        self.relative_target = protection.take_profit_pct
        self.refresh_relative_protection()
        direction = 1 if self.position > 0 else -1
        if protection.stop_loss_distance is not None:
            self.stop_price = self.average_entry - direction * protection.stop_loss_distance
        if protection.take_profit_distance is not None:
            self.targets = [
                (self.average_entry + direction * protection.take_profit_distance, quantity)
            ]
        if (self.stop_price is not None and self.stop_price <= 0) or any(
            price <= 0 for price, _ in self.targets
        ):
            raise ValueError("Protective distances produced nonpositive price levels")

    def refresh_relative_protection(self) -> None:
        direction = 1 if self.position > 0 else -1
        if self.relative_stop is not None:
            self.stop_price = self.average_entry * (1 - direction * self.relative_stop / 100)
        if self.relative_target is not None:
            self.targets = [
                (
                    self.average_entry * (1 + direction * self.relative_target / 100),
                    abs(self.position),
                )
            ]

    def record(self, timestamp: int, order_id: str, outcome: str) -> None:
        event: dict[str, object] = {
            "timestamp_ms": timestamp,
            "order_id": order_id,
            "outcome": outcome,
        }
        if outcome in ("submit", "update"):
            order = self.active[order_id]
            event.update(limit_price=order.price, side=order.side.value)
        self.events.append(event)


def execute_order_event(  # noqa: C901
    state: EventOrderState,
    *,
    symbol: str,
    timestamp_ms: int,
    prices: Sequence[float],
    config: EventOrderConfig,
) -> EventOrderState:
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
    if config.daily_schedule is not None and base.position and base.entry_timestamp_ms is not None:
        if timestamp_ms >= config.daily_schedule.exit_timestamp(base.entry_timestamp_ms):
            side = OrderSide.SELL if base.position > 0 else OrderSide.BUY
            _fill(
                base,
                symbol,
                timestamp_ms,
                side,
                abs(base.position),
                opening + config.quote_offset(side),
                config,
                reason=ExitReason.SIGNAL,
            )
            for key in base.active:
                base.record(timestamp_ms, key, "schedule_cancelled")
            base.active.clear()
    paths = [(opening, high, low, closing), (opening, low, high, closing)]
    outcomes = [
        _path(
            replace(
                base,
                active=dict(base.active),
                targets=list(base.targets),
                fills=list(base.fills),
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
    multiplier = config.instrument.contract_multiplier if config.instrument else 1.0
    score = [s.cash + s.position * closing * multiplier for s in outcomes]
    choose_right = (
        score[1] > score[0]
        if config.policy == IntrabarExecutionPolicy.OPTIMISTIC
        else score[1] < score[0]
    )
    result = right if choose_right else left
    result.last_price = closing
    if different:
        result.ambiguous_minutes += 1
        result.record(timestamp_ms, "", "ambiguous")
    result.fills = state.fills + result.fills
    result.events = state.events + result.events
    return result


def _path(
    state: EventOrderState,
    path: Sequence[float],
    symbol: str,
    timestamp: int,
    config: EventOrderConfig,
) -> EventOrderState:
    current = path[0]
    _at_price(state, current, symbol, timestamp, config)
    for end in path[1:]:
        while current != end and not state.depleted:
            levels = [
                order.price - config.quote_offset(order.side)
                for order in state.active.values()
                if not order.market
            ]
            if state.position:
                side = OrderSide.SELL if state.position > 0 else OrderSide.BUY
                offset = config.quote_offset(side)
                levels.extend(price - offset for price, _ in state.targets)
                if state.stop_price is not None:
                    levels.append(state.stop_price - offset)
                if config.instrument is not None and config.sizing is not None:
                    levels.append(
                        -(config.initial_capital + state.cash)
                        / (state.position * config.instrument.contract_multiplier)
                    )
            crossed = [
                level
                for level in levels
                if (current < level <= end if end > current else end <= level < current)
            ]
            current = (min(crossed) if end > current else max(crossed)) if crossed else end
            _at_price(state, current, symbol, timestamp, config)
    return state


def _at_price(  # noqa: C901
    state: EventOrderState,
    price: float,
    symbol: str,
    timestamp: int,
    config: EventOrderConfig,
) -> None:
    if _deplete(state, price, symbol, timestamp, config):
        return
    _protect(state, price, symbol, timestamp, config)
    if _deplete(state, price, symbol, timestamp, config):
        return
    for key in list(state.active):
        order = state.active.get(key)
        if order is None:
            continue
        quote = price + config.quote_offset(order.side)
        touched = quote <= order.price if order.side == OrderSide.BUY else quote >= order.price
        if not touched and not order.market:
            continue
        del state.active[key]
        direction = 1 if order.side == OrderSide.BUY else -1
        quantity = order.quantity
        if order.only_when_flat and state.position:
            state.record(timestamp, key, "constraint_cancelled")
            continue
        if order.reduce_only:
            quantity = min(quantity, abs(state.position)) if state.position * direction < 0 else 0
        if not quantity:
            state.record(timestamp, key, "reduce_only_cancelled")
            continue
        if state.position * direction > 0 and order.protection is not None:
            protection = order.protection
            if config.stop_loss is not None and config.stop_loss.mode != "strategy":
                protection = replace(
                    protection,
                    stop_price=state.stop_price,
                    stop_loss_pct=None,
                    stop_loss_distance=None,
                )
            if config.take_profit is not None and config.take_profit.mode != "strategy":
                from domain.orders import TakeProfitTier

                protection = replace(
                    protection,
                    take_profits=tuple(
                        TakeProfitTier(level, fraction=1.0) for level, _ in state.targets
                    ),
                    take_profit_pct=None,
                    take_profit_distance=None,
                )
            order = replace(order, protection=protection)
        new_position = state.position + direction * quantity
        increasing = state.position * direction >= 0 or quantity > abs(state.position)
        if state.entry_day != timestamp // DAY_MS:
            state.entry_day = timestamp // DAY_MS
            state.entries_today = 0
        invalid = (
            (config.allowed_directions == AllowedDirections.LONG_ONLY and new_position < 0)
            or (config.allowed_directions == AllowedDirections.SHORT_ONLY and new_position > 0)
            or (
                config.max_position_quantity is not None
                and abs(new_position) > config.max_position_quantity
                and abs(new_position) > abs(state.position)
            )
        )
        if increasing:
            invalid |= config.daily_schedule is not None and not config.daily_schedule.allows_entry(
                timestamp
            )
            invalid |= (
                config.max_entries_per_day is not None
                and state.entries_today >= config.max_entries_per_day
            )
        if invalid:
            state.record(timestamp, key, "constraint_cancelled")
            continue
        if increasing and config.instrument is not None and config.sizing is not None:
            spec = config.instrument
            equity = (
                config.initial_capital
                + state.cash
                + state.position * price * spec.contract_multiplier
            )
            fill_price = quote * (1 + direction * config.slippage_bps / 10000)
            if not order.market:
                fill_price = (
                    min(fill_price, order.price) if direction > 0 else max(fill_price, order.price)
                )
            required = spec.notional(new_position, fill_price) / config.sizing.leverage
            equity -= spec.notional(quantity, fill_price) * config.commission_bps / 10000
            equity -= direction * quantity * (fill_price - price) * spec.contract_multiplier
            stop = order.protection.stop_price if order.protection else None
            invalid_stop = config.sizing.mode in ("risk", "equity_risk") and (
                stop is None or direction * (fill_price - stop) <= 0
            )
            if invalid_stop or required > equity - state.reserved_margin():
                if state.position * direction < 0:
                    _fill(
                        state,
                        symbol,
                        timestamp,
                        order.side,
                        abs(state.position),
                        quote,
                        config,
                        limit=None if order.market else order.price,
                    )
                state.record(
                    timestamp, key, "invalid_stop" if invalid_stop else "insufficient_margin"
                )
                continue
        _fill(
            state,
            symbol,
            timestamp,
            order.side,
            quantity,
            quote,
            config,
            limit=None if order.market else order.price,
        )
        if increasing:
            state.entries_today += 1
        state.record(timestamp, key, "filled")
        if config.instrument is not None and increasing:
            stop = order.protection.stop_price if order.protection else state.stop_price
            fill_price = state.fills[-1].price
            risk_at_fill = (
                (
                    direction
                    * (fill_price - stop)
                    * min(quantity, abs(state.position))
                    * config.instrument.contract_multiplier
                )
                if stop is not None
                else None
            )
            state.events[-1].update(
                fill_price=fill_price,
                quantity=quantity,
                stop_price=stop,
                risk_at_fill=risk_at_fill,
                risk_difference=(
                    (risk_at_fill - order.planned_risk)
                    if risk_at_fill is not None and order.planned_risk is not None
                    else None
                ),
            )
        if order.oco_group is not None:
            for sibling, pending in list(state.active.items()):
                if pending.oco_group == order.oco_group:
                    del state.active[sibling]
                    state.record(timestamp, sibling, "oco_cancelled")
        if order.protection is not None and state.position:
            protection = order.protection
            if not increasing:
                if config.stop_loss is not None and config.stop_loss.mode != "strategy":
                    protection = replace(
                        protection,
                        stop_price=state.stop_price,
                        stop_loss_pct=None,
                        stop_loss_distance=None,
                    )
                if config.take_profit is not None and config.take_profit.mode != "strategy":
                    from domain.orders import TakeProfitTier

                    protection = replace(
                        protection,
                        take_profits=tuple(
                            TakeProfitTier(level, quantity=min(quantity, abs(state.position)))
                            for level, quantity in state.targets
                        ),
                        take_profit_pct=None,
                        take_profit_distance=None,
                    )
            state.set_protection(
                protection,
                (
                    abs(state.position)
                    if config.take_profit is not None and config.take_profit.mode != "strategy"
                    else order.quantity
                ),
            )
            state.fills[-1] = replace(
                state.fills[-1],
                stop_loss_price=state.stop_price,
                take_profit_price=state.targets[0][0] if state.targets else None,
            )
        _protect(state, price, symbol, timestamp, config)
        if _deplete(state, price, symbol, timestamp, config):
            return


def _protect(
    state: EventOrderState,
    price: float,
    symbol: str,
    timestamp: int,
    config: EventOrderConfig,
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
                take_profit_override=level,
            )


def _fill(
    state: EventOrderState,
    symbol: str,
    timestamp: int,
    side: OrderSide,
    quantity: float,
    raw_price: float,
    config: EventOrderConfig,
    limit: float | None = None,
    reason: ExitReason | None = None,
    take_profit_override: float | None = None,
) -> None:
    direction = 1 if side == OrderSide.BUY else -1
    price = raw_price * (1 + direction * config.slippage_bps / 10_000)
    if limit is not None:
        price = min(price, limit) if direction > 0 else max(price, limit)
    if price <= 0:
        raise ValueError("Execution costs produced a nonpositive fill price")
    multiplier = config.instrument.contract_multiplier if config.instrument else 1.0
    fees = quantity * price * multiplier * config.commission_bps / 10_000
    before = state.position
    state.position += direction * quantity
    if before * direction >= 0:
        state.average_entry = (abs(before) * state.average_entry + quantity * price) / abs(
            state.position
        )
    elif before * state.position < 0:
        state.average_entry = price
    if before == 0 or before * state.position < 0:
        state.entry_timestamp_ms = timestamp
    state.cash -= direction * quantity * price * multiplier + fees
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
            (
                take_profit_override
                if take_profit_override is not None
                else (state.targets[0][0] if state.targets else None)
            ),
        )
    )
    if before * state.position <= 0:
        state.stop_price = None
        state.targets.clear()
        state.relative_stop = None
        state.relative_target = None
    if state.position:
        state.refresh_relative_protection()
    else:
        state.entry_timestamp_ms = None
        state.average_entry = 0.0


def _deplete(
    state: EventOrderState, price: float, symbol: str, timestamp: int, config: EventOrderConfig
) -> bool:
    if state.depleted:
        return True
    if config.instrument is None or config.sizing is None:
        return False
    equity = (
        config.initial_capital
        + state.cash
        + state.position * price * config.instrument.contract_multiplier
    )
    if equity > 1e-9:
        return False
    for key in state.active:
        state.record(timestamp, key, "account_depleted_cancelled")
    state.active.clear()
    if state.position:
        side = OrderSide.SELL if state.position > 0 else OrderSide.BUY
        _fill(
            state,
            symbol,
            timestamp,
            side,
            abs(state.position),
            price + config.quote_offset(side),
            config,
            reason=ExitReason.ACCOUNT_DEPLETED,
        )
    state.depleted = True
    state.record(timestamp, "", "account_depleted")
    return True
