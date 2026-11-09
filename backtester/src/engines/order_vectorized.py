"""Array strategy evaluation and minute execution for order-based strategies."""

import pandas as pd
from data.order_bars import (
    close_timestamps,
    feature_matrix,
    resolve_order_expiry,
    resolve_order_ticks,
)
from domain.enums import IntrabarExitPolicy
from domain.orders import IntrabarExecutionPolicy
from domain.types import BacktestRequest, BacktestResult
from execution.order_scan import scan_orders
from execution.orders import OrderExecutionConfig
from execution.portfolio import build_equity_curve
from execution.trades import build_trades_from_fills
from reporting.metrics import compute_metrics
from strategies.base import StrategyDefinition


def run_order_vectorized(
    *,
    request: BacktestRequest,
    strategy_bars: pd.DataFrame,
    execution_bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> BacktestResult:
    model = strategy.order_model
    if model is None:
        raise ValueError("Order execution requires an order strategy")
    symbol = request.symbols[0]
    closes = close_timestamps(strategy_bars, request.timeframe)
    commands = [
        resolve_order_ticks(
            resolve_order_expiry(command, request.timeframe), request.market_min_move
        )
        for command in model.build_commands(feature_matrix(strategy_bars, symbol), closes)
    ]
    boundaries = set(closes)
    if any(command.effective_at_ms not in boundaries for command in commands):
        raise ValueError("Order commands must originate at completed strategy-candle boundaries")
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
    result = scan_orders(
        symbol=symbol,
        timestamp_ms=execution_bars.timestamp_ms.astype(int).tolist(),
        ohlc=execution_bars[["open", "high", "low", "close"]].to_numpy(dtype=float),
        commands=commands,
        start_ms=max(request.start_ms, int(strategy_bars.timestamp_ms.iloc[0])),
        end_ms=request.end_ms,
        config=OrderExecutionConfig(
            instrument=request.instrument,
            sizing=config.sizing,
            stop_loss=config.stop_loss,
            take_profit=config.take_profit,
            initial_capital=request.initial_capital,
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
        ),
    )
    equity = build_equity_curve(
        symbol=symbol,
        timestamp_ms=execution_bars.timestamp_ms,
        close_prices=execution_bars.close,
        executed_delta=result.executed_delta,
        executed_notional=result.executed_notional,
        executed_fees=result.executed_fees,
        initial_capital=request.initial_capital,
        contract_multiplier=request.instrument.contract_multiplier if request.instrument else 1.0,
    )
    depleted = next(
        (
            event["timestamp_ms"]
            for event in result.events
            if event["outcome"] == "account_depleted"
        ),
        None,
    )
    if isinstance(depleted, int):
        equity = [point for point in equity if point.timestamp_ms <= int(depleted)]
    trades = build_trades_from_fills(
        result.fills,
        protection_at_exit=True,
        contract_multiplier=request.instrument.contract_multiplier if request.instrument else 1.0,
    )
    return BacktestResult(
        request=request,
        fills=result.fills,
        trades=trades,
        equity_curve=equity,
        metrics=compute_metrics(equity_curve=equity, trades=trades),
        diagnostics={
            "engine": "vectorized",
            "execution_mode": "orders",
            "execution_timeframe": "M1",
            "termination_reason": (
                "account_depleted"
                if any(event["outcome"] == "account_depleted" for event in result.events)
                else None
            ),
            "order_events": result.events,
            "intrabar_execution_policy": policy.value,
            "intrabar_ambiguous_bar_count": result.ambiguous_minutes,
        },
    )
