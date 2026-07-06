"""True vectorized bar-mode backtest engine."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
from domain.enums import (
    BacktestEngine,
    DataGranularity,
    ExitReason,
    FillTiming,
    OrderSide,
    PriceSource,
    SignalTiming,
    TradeAccountingPolicy,
)
from domain.types import (
    BacktestRequest,
    BacktestResult,
    ExecutionArrayBundle,
    FeatureMatrix,
    Fill,
    ProtectiveExitSpec,
    SignalMatrix,
)
from execution.fills import (
    FillGenerationResult,
    generate_fills_from_targets,
    generate_fills_from_targets_with_protective_exits,
)
from execution.portfolio import build_equity_curve
from execution.trades import build_trades_from_fills
from reporting.metrics import compute_metrics
from strategies.base import StrategyDefinition

REQUIRED_BAR_COLUMNS = {
    "timestamp_ms",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def run_vectorized_backtest(
    *,
    request: BacktestRequest,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> BacktestResult:
    """Run a vectorized bar backtest for one symbol."""
    _validate_vectorized_request(request)

    symbol = request.symbols[0]
    normalized = _normalize_bars(bars=bars, symbol=symbol)

    feature_matrix = _build_feature_matrix(normalized)
    execution_targets = strategy.build_execution_targets(feature_matrix)
    timestamp_ms = normalized["timestamp_ms"].to_numpy(dtype="int64")
    target_values = _extract_target_values(
        execution_targets=execution_targets,
        symbol=symbol,
        expected_size=timestamp_ms.size,
    )

    open_prices = normalized["open"].to_numpy(dtype="float64")
    high_prices = normalized["high"].to_numpy(dtype="float64")
    low_prices = normalized["low"].to_numpy(dtype="float64")
    close_prices = normalized["close"].to_numpy(dtype="float64")

    protective_exit = _protective_exit_for_strategy(strategy)
    if protective_exit is None:
        fill_result = generate_fills_from_targets(
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            open_prices=open_prices,
            target_quantity=target_values,
            gap_policy=request.execution.gap_policy,
            slippage_bps=float(request.execution.slippage_bps),
            commission_bps=float(request.execution.commission_bps),
        )
    else:
        signal_matrix = strategy.require_v1_parity_model().build_signals(feature_matrix)
        signal_values = _extract_signal_values(
            signal_matrix=signal_matrix,
            symbol=symbol,
            expected_size=timestamp_ms.size,
        )
        fill_result = generate_fills_from_targets_with_protective_exits(
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            open_prices=open_prices,
            high_prices=high_prices,
            low_prices=low_prices,
            target_quantity=target_values,
            signal_values=signal_values,
            stop_loss_pct=protective_exit.stop_loss_pct,
            take_profit_pct=protective_exit.take_profit_pct,
            intrabar_exit_policy=request.execution.intrabar_exit_policy,
            gap_policy=request.execution.gap_policy,
            slippage_bps=float(request.execution.slippage_bps),
            commission_bps=float(request.execution.commission_bps),
        )

    equity_curve = build_equity_curve(
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        close_prices=close_prices,
        executed_delta=fill_result.executed_delta,
        executed_notional=fill_result.executed_notional,
        executed_fees=fill_result.executed_fees,
        initial_capital=request.initial_capital,
    )

    trades = build_trades_from_fills(fill_result.fills)
    metrics = compute_metrics(equity_curve=equity_curve, trades=trades)

    return BacktestResult(
        request=request,
        fills=fill_result.fills,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        diagnostics=_build_diagnostics(
            request=request,
            strategy=strategy,
            normalized=normalized,
            symbol=symbol,
            fill_result=fill_result,
        ),
    )


def _validate_vectorized_request(request: BacktestRequest) -> None:
    execution = request.execution
    constraints = (
        (
            request.engine == BacktestEngine.VECTORIZED,
            "Vectorized engine requires engine=vectorized",
        ),
        (
            request.data_granularity == DataGranularity.BAR,
            "Vectorized engine supports bar data only",
        ),
        (
            len(request.symbols) == 1,
            "Vectorized engine supports exactly one symbol per run",
        ),
        (
            execution.signal_timing == SignalTiming.CLOSE,
            "Vectorized M3 baseline supports signal_timing=close only",
        ),
        (
            execution.fill_timing == FillTiming.NEXT_OPEN,
            "Vectorized M3 baseline supports fill_timing=next_open only",
        ),
        (
            execution.price_source == PriceSource.OPEN,
            "Vectorized M3 baseline supports price_source=open only",
        ),
        (
            not execution.allow_partial_fills,
            "Vectorized M3 baseline does not support allow_partial_fills=True",
        ),
        (
            execution.trade_accounting_policy == TradeAccountingPolicy.AVERAGE_COST,
            "Vectorized M3 baseline supports trade_accounting_policy=average_cost only",
        ),
    )
    for is_valid, message in constraints:
        if not is_valid:
            raise ValueError(message)


def _extract_target_values(
    *,
    execution_targets: ExecutionArrayBundle,
    symbol: str,
    expected_size: int,
) -> np.ndarray:
    target = execution_targets.target_quantity_by_symbol.get(symbol)
    if target is None:
        raise ValueError(f"Strategy did not produce execution targets for symbol {symbol}")

    target_values = np.asarray(target, dtype=np.float64)
    if target_values.size != expected_size:
        raise ValueError(
            f"Strategy target quantity length must match executable bar count for symbol {symbol}"
        )
    if not np.isfinite(target_values).all():
        raise ValueError(f"Strategy produced non-finite target quantities for symbol {symbol}")
    if np.any(target_values < 0.0):
        raise ValueError(
            "Vectorized M3 baseline is long-only and requires non-negative target quantities "
            f"for symbol {symbol}"
        )
    return target_values


def _extract_signal_values(
    *,
    signal_matrix: SignalMatrix,
    symbol: str,
    expected_size: int,
) -> np.ndarray:
    signals = signal_matrix.signals_by_symbol.get(symbol)
    if signals is None:
        raise ValueError(f"Strategy did not produce signals for symbol {symbol}")

    signal_values = np.asarray(signals, dtype=np.int64)
    if signal_values.size != expected_size:
        raise ValueError(
            f"Strategy signal length must match executable bar count for symbol {symbol}"
        )
    return signal_values


def _protective_exit_for_strategy(strategy: StrategyDefinition) -> ProtectiveExitSpec | None:
    if strategy.bar_model is None:
        return None
    protective_exit = strategy.bar_model.protective_exit
    if protective_exit.stop_loss_pct is None and protective_exit.take_profit_pct is None:
        return None
    return protective_exit


def _build_diagnostics(
    *,
    request: BacktestRequest,
    strategy: StrategyDefinition,
    normalized: pd.DataFrame,
    symbol: str,
    fill_result: FillGenerationResult,
) -> dict[str, float | int | str]:
    return {
        "engine": "vectorized",
        "bars": int(len(normalized)),
        "symbol": symbol,
        "strategy_id": strategy.strategy_id,
        "fill_timing": request.execution.fill_timing.value,
        "gap_policy": request.execution.gap_policy.value,
        "intrabar_exit_policy": request.execution.intrabar_exit_policy.value,
        "commission_bps": float(request.execution.commission_bps),
        "slippage_bps": float(request.execution.slippage_bps),
        "total_fees": float(fill_result.executed_fees.sum()),
        "total_slippage_cost": float(fill_result.total_slippage_cost),
        "stop_loss_exit_count": _exit_fill_count(
            fills=fill_result.fills,
            exit_reason=ExitReason.STOP_LOSS,
        ),
        "take_profit_exit_count": _exit_fill_count(
            fills=fill_result.fills,
            exit_reason=ExitReason.TAKE_PROFIT,
        ),
        "signal_exit_count": _signal_exit_fill_count(fill_result.fills),
        "intrabar_ambiguous_bar_count": int(fill_result.intrabar_ambiguous_bar_count),
        "invalid_open_count": int(fill_result.invalid_open_count),
        "deferred_delta_count": int(fill_result.deferred_delta_count),
        "expired_delta_count": int(fill_result.expired_delta_count),
        "executed_deferred_count": int(fill_result.executed_deferred_count),
        "tail_expired_delta_count": int(fill_result.tail_expired_delta_count),
    }


def _exit_fill_count(*, fills: list[Fill], exit_reason: ExitReason) -> int:
    return sum(
        1 for fill in fills if fill.side == OrderSide.SELL and fill.exit_reason == exit_reason
    )


def _signal_exit_fill_count(fills: list[Fill]) -> int:
    return sum(
        1
        for fill in fills
        if fill.side == OrderSide.SELL
        and (fill.exit_reason is None or fill.exit_reason == ExitReason.SIGNAL)
    )


def _normalize_bars(*, bars: pd.DataFrame, symbol: str) -> pd.DataFrame:
    missing_columns = REQUIRED_BAR_COLUMNS - set(bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"bars is missing required columns: {missing}")

    filtered = bars.loc[bars["symbol"] == symbol].copy()
    if filtered.empty:
        raise ValueError(f"No bars found for symbol {symbol}")

    filtered.sort_values("timestamp_ms", inplace=True)
    filtered.reset_index(drop=True, inplace=True)

    return filtered


def _build_feature_matrix(bars: pd.DataFrame) -> FeatureMatrix:
    symbol = str(bars["symbol"].iloc[0])

    feature_columns = [col for col in bars.columns if col not in {"timestamp_ms", "symbol"}]
    features: Dict[str, Dict[str, list[float]]] = {
        symbol: {col: bars[col].astype(float).to_list() for col in feature_columns}
    }

    return FeatureMatrix(
        timestamp_ms=bars["timestamp_ms"].astype(int).to_list(),
        features_by_symbol=features,
    )
