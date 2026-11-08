"""Sequential completed-candle decisions and independent order/portfolio updates."""

import pandas as pd
from data.order_bars import close_timestamps, resolve_order_expiry, resolve_order_ticks
from domain.enums import GapPolicy, IntrabarExitPolicy
from domain.orders import IntrabarExecutionPolicy
from domain.types import BacktestRequest, BacktestResult, PortfolioSnapshot
from execution.trades import build_trades_from_fills
from reporting.metrics import compute_metrics
from strategies.base import StrategyDefinition

from engines.order_events import EventOrderConfig, EventOrderState, execute_order_event


def run_order_event_driven(  # noqa: C901
    *,
    request: BacktestRequest,
    strategy_bars: pd.DataFrame,
    execution_bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> BacktestResult:  # noqa: C901
    model = strategy.order_model
    if model is None:
        raise ValueError("Order execution requires an order strategy")
    config = request.execution
    policy = (
        config.intrabar_execution_policy
        or {
            IntrabarExitPolicy.CONSERVATIVE: IntrabarExecutionPolicy.CONSERVATIVE,
            IntrabarExitPolicy.STOP_FIRST: IntrabarExecutionPolicy.CONSERVATIVE,
            IntrabarExitPolicy.TAKE_PROFIT_FIRST: IntrabarExecutionPolicy.OPTIMISTIC,
            IntrabarExitPolicy.ERROR: IntrabarExecutionPolicy.ERROR,
        }[config.intrabar_exit_policy]
    )
    matching = EventOrderConfig(
        spread=config.spread,
        candle_quote=str(config.candle_quote),
        policy=policy,
        slippage_bps=config.slippage_bps,
        commission_bps=config.commission_bps,
        gap_policy=config.gap_policy,
        allowed_directions=config.allowed_directions,
        max_position_quantity=config.max_position_quantity,
        daily_schedule=config.daily_schedule,
        max_entries_per_day=config.max_entries_per_day,
    )
    closes = close_timestamps(strategy_bars, request.timeframe)
    decisions = strategy_bars.drop(columns=["symbol", "timestamp_ms"]).to_dict("records")
    state = EventOrderState()
    cursor = 0
    previous = None
    fills = []
    events = []
    curve = []
    previous_end = max(request.start_ms, int(strategy_bars.timestamp_ms.iloc[0]))
    symbol = request.symbols[0]

    def decide(boundary: int) -> None:
        nonlocal cursor, previous
        current = {str(key): float(value) for key, value in decisions[cursor].items()}
        for command in model.evaluate_close(boundary, previous, current):
            if command.effective_at_ms != boundary:
                raise ValueError("Order commands must originate at the current strategy close")
            state.command(
                resolve_order_ticks(
                    resolve_order_expiry(command, request.timeframe), request.market_min_move
                )
            )
        previous = current
        cursor += 1

    for timestamp_value, opening, high, low, closing in execution_bars[
        ["timestamp_ms", "open", "high", "low", "close"]
    ].itertuples(index=False, name=None):
        timestamp = int(timestamp_value)
        while cursor < len(closes) and closes[cursor] < timestamp:
            decide(closes[cursor])
        if timestamp > previous_end:
            if config.gap_policy == GapPolicy.ERROR:
                raise ValueError(f"Missing minute execution data at {previous_end}")
            state.record(previous_end, "", "execution_gap")
            if config.gap_policy == GapPolicy.EXPIRE:
                for key in state.active:
                    state.record(previous_end, key, "gap_expired")
                state.active.clear()
        while cursor < len(closes) and closes[cursor] == timestamp:
            decide(closes[cursor])
        state = execute_order_event(
            state,
            symbol=symbol,
            timestamp_ms=timestamp,
            prices=(float(opening), float(high), float(low), float(closing)),
            config=matching,
        )
        fills.extend(state.fills)
        events.extend(state.events)
        state.fills = []
        state.events = []
        curve.append(
            PortfolioSnapshot(
                timestamp,
                request.initial_capital + state.cash,
                request.initial_capital + state.cash + state.position * float(closing),
                {symbol: state.position} if state.position else {},
            )
        )
        previous_end = timestamp + 60_000
    if previous_end < request.end_ms:
        if config.gap_policy == GapPolicy.ERROR:
            raise ValueError(f"Missing minute execution data at {previous_end}")
        state.record(previous_end, "", "execution_gap")
    for key in state.active:
        state.record(request.end_ms, key, "run_end_expired")
    while cursor < len(closes):
        current = {str(key): float(value) for key, value in decisions[cursor].items()}
        for command in model.evaluate_close(closes[cursor], previous, current):
            state.record(request.end_ms, command.order_id, "run_end_unexecuted")
        previous = current
        cursor += 1
    events.extend(state.events)
    trades = build_trades_from_fills(fills, protection_at_exit=True)
    return BacktestResult(
        request=request,
        fills=fills,
        trades=trades,
        equity_curve=curve,
        metrics=compute_metrics(equity_curve=curve, trades=trades),
        diagnostics={
            "engine": "event_driven",
            "execution_mode": "orders",
            "execution_timeframe": "M1",
            "order_events": events,
            "intrabar_execution_policy": policy.value,
            "intrabar_ambiguous_bar_count": state.ambiguous_minutes,
        },
    )
