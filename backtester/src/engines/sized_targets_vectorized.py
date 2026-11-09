"""Vectorized execution of sized target strategy entries."""

from domain.enums import AllowedDirections, IntrabarExitPolicy, OrderSide
from domain.orders import (
    IntrabarExecutionPolicy,
    LimitOrder,
    OrderAction,
    OrderCommand,
    OrderProtection,
)
from domain.types import BacktestResult, PortfolioSnapshot
from execution.orders import OrderExecutionConfig, OrderExecutionState, execute_minute
from execution.trades import build_trades_from_fills
from reporting.metrics import compute_metrics


def run_sized_targets(request, strategy, decisions):  # noqa: C901
    """Consume causal completed-candle decisions; fill pending intent next open."""
    instrument = request.instrument
    if instrument is None:
        raise ValueError("Sized execution requires instrument specifications")
    execution = request.execution
    policy = (
        execution.intrabar_execution_policy
        or {
            IntrabarExitPolicy.CONSERVATIVE: IntrabarExecutionPolicy.CONSERVATIVE,
            IntrabarExitPolicy.STOP_FIRST: IntrabarExecutionPolicy.CONSERVATIVE,
            IntrabarExitPolicy.TAKE_PROFIT_FIRST: IntrabarExecutionPolicy.OPTIMISTIC,
            IntrabarExitPolicy.ERROR: IntrabarExecutionPolicy.ERROR,
        }[execution.intrabar_exit_policy]
    )
    config = OrderExecutionConfig(
        instrument=instrument,
        sizing=execution.sizing,
        stop_loss=execution.stop_loss,
        take_profit=execution.take_profit,
        initial_capital=request.initial_capital,
        candle_quote="mid",
        policy=policy,
        commission_bps=execution.commission_bps,
        slippage_bps=execution.slippage_bps,
        gap_policy=execution.gap_policy,
        allowed_directions=execution.allowed_directions,
        daily_schedule=execution.daily_schedule,
        max_entries_per_day=execution.max_entries_per_day,
    )
    state = OrderExecutionState(config=config)
    symbol = request.symbols[0]
    model = strategy.require_v1_parity_model()
    protection = OrderProtection(
        stop_loss_pct=model.protective_exit.stop_loss_pct,
        take_profit_pct=model.protective_exit.take_profit_pct,
    )
    fills, events, curve = [], [], []
    for timestamp, opening, high, low, closing, signal, boundary, target_quantity in decisions:
        state = execute_minute(
            state,
            symbol=symbol,
            timestamp_ms=timestamp,
            prices=(opening, high, low, closing),
            config=config,
        )
        fills.extend(state.fills)
        events.extend(state.events)
        state.fills = []
        state.events = []
        curve.append(
            PortfolioSnapshot(
                timestamp,
                request.initial_capital + state.cash,
                request.initial_capital
                + state.cash
                + state.position * closing * instrument.contract_multiplier,
                {symbol: state.position} if state.position else {},
            )
        )
        if state.depleted:
            break
        if not signal:
            continue
        direction = 0 if target_quantity == 0 else (1 if target_quantity > 0 else -1)
        if (direction > 0 and execution.allowed_directions == AllowedDirections.SHORT_ONLY) or (
            direction < 0 and execution.allowed_directions == AllowedDirections.LONG_ONLY
        ):
            direction = 0
        strategy_sizing = execution.sizing is not None and execution.sizing.mode == "strategy"
        if direction and state.position * direction > 0 and not strategy_sizing:
            continue
        for key in list(state.active):
            state.command(OrderCommand(boundary, OrderAction.CANCEL, key))
        if not direction and not state.position:
            continue
        side = (
            OrderSide.BUY
            if (direction > 0 or (direction == 0 and state.position < 0))
            else OrderSide.SELL
        )
        key = f"target-{timestamp}"
        quantity = (
            abs(target_quantity) + (abs(state.position) if state.position * direction < 0 else 0.0)
            if direction
            else abs(state.position)
        )
        reduce_only = not direction
        if strategy_sizing:
            delta = target_quantity - state.position
            if delta == 0:
                continue
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            quantity = abs(delta)
            reduce_only = state.position * delta < 0 and quantity <= abs(state.position)
        state.command(
            OrderCommand(
                boundary,
                OrderAction.SUBMIT,
                key,
                LimitOrder(
                    key,
                    side,
                    closing,
                    quantity,
                    reduce_only=reduce_only,
                    protection=protection if direction else None,
                    market=True,
                ),
            )
        )
        events.extend(state.events)
        state.events = []
    if not curve:
        raise ValueError("No executable bars remain after warmup")
    for key in state.active:
        state.record(curve[-1].timestamp_ms, key, "run_end_expired")
    events.extend(state.events)
    trades = build_trades_from_fills(
        fills, protection_at_exit=True, contract_multiplier=instrument.contract_multiplier
    )
    return BacktestResult(
        request,
        fills,
        trades,
        curve,
        compute_metrics(equity_curve=curve, trades=trades),
        {
            "engine": "vectorized",
            "order_events": events,
            "termination_reason": "account_depleted" if state.depleted else None,
            "intrabar_ambiguous_bar_count": state.ambiguous_minutes,
        },
    )
