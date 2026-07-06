"""Backtest reporting metrics."""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
from domain.enums import TradeDirection
from domain.types import PortfolioSnapshot, Trade


def compute_metrics(
    *,
    equity_curve: Sequence[PortfolioSnapshot],
    trades: Sequence[Trade],
) -> Dict[str, float]:
    """Compute minimal M1 metrics."""

    if not equity_curve:
        return {
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0.0,
            **_direction_metrics(trades=trades),
        }

    equity = np.asarray([snap.equity for snap in equity_curve], dtype=np.float64)
    initial = float(equity[0])
    final = float(equity[-1])

    total_return_pct = 0.0 if initial == 0.0 else ((final / initial) - 1.0) * 100.0

    running_peak = np.maximum.accumulate(equity)
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown = np.where(running_peak > 0.0, (equity - running_peak) / running_peak, 0.0)
    max_drawdown_pct = float(np.min(drawdown) * 100.0)

    return {
        "total_return_pct": float(total_return_pct),
        "max_drawdown_pct": max_drawdown_pct,
        "trade_count": float(len(trades)),
        **_direction_metrics(trades=trades),
    }


def _direction_metrics(*, trades: Sequence[Trade]) -> Dict[str, float]:
    long_trades = [trade for trade in trades if trade.trade_direction == TradeDirection.LONG]
    short_trades = [trade for trade in trades if trade.trade_direction == TradeDirection.SHORT]

    return {
        "long_trade_count": float(len(long_trades)),
        "short_trade_count": float(len(short_trades)),
        "long_win_rate_pct": _win_rate_pct(long_trades),
        "short_win_rate_pct": _win_rate_pct(short_trades),
        "long_realized_pnl": float(sum(trade.realized_pnl for trade in long_trades)),
        "short_realized_pnl": float(sum(trade.realized_pnl for trade in short_trades)),
    }


def _win_rate_pct(trades: Sequence[Trade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for trade in trades if trade.realized_pnl > 0.0)
    return float((wins / len(trades)) * 100.0)
