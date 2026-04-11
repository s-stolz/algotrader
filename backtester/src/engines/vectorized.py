"""True vectorized bar-mode backtest engine."""

from __future__ import annotations

from typing import Dict

import pandas as pd
from domain.enums import DataGranularity
from domain.types import BacktestRequest, BacktestResult, FeatureMatrix
from execution.fills import generate_fills_from_targets
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

    if request.data_granularity != DataGranularity.BAR:
        raise ValueError("M1 vectorized engine supports bar data only")

    if len(request.symbols) != 1:
        raise ValueError("M1 vectorized engine supports exactly one symbol per run")

    symbol = request.symbols[0]
    normalized = _normalize_bars(bars=bars, symbol=symbol)

    feature_matrix = _build_feature_matrix(normalized)
    execution_targets = strategy.build_execution_targets(feature_matrix)

    target = execution_targets.target_quantity_by_symbol.get(symbol)
    if target is None:
        raise ValueError(f"Strategy did not produce execution targets for symbol {symbol}")

    timestamp_ms = normalized["timestamp_ms"].to_numpy(dtype="int64")
    open_prices = normalized["open"].to_numpy(dtype="float64")

    fills, executed_delta = generate_fills_from_targets(
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        open_prices=open_prices,
        target_quantity=target,
        gap_policy=request.execution.gap_policy,
    )

    equity_curve = build_equity_curve(
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        open_prices=open_prices,
        executed_delta=executed_delta,
        initial_capital=request.initial_capital,
    )

    trades = build_trades_from_fills(fills)
    metrics = compute_metrics(equity_curve=equity_curve, trades=trades)

    diagnostics = {
        "engine": "vectorized",
        "bars": int(len(normalized)),
        "symbol": symbol,
        "strategy_id": strategy.strategy_id,
    }

    return BacktestResult(
        request=request,
        fills=fills,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        diagnostics=diagnostics,
    )


def _normalize_bars(*, bars: pd.DataFrame, symbol: str) -> pd.DataFrame:
    missing_columns = REQUIRED_BAR_COLUMNS - set(bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"bars is missing required columns: {missing}")

    filtered = bars.loc[bars["symbol"] == symbol, sorted(REQUIRED_BAR_COLUMNS)].copy()
    if filtered.empty:
        raise ValueError(f"No bars found for symbol {symbol}")

    filtered.sort_values("timestamp_ms", inplace=True)
    filtered.reset_index(drop=True, inplace=True)

    return filtered


def _build_feature_matrix(bars: pd.DataFrame) -> FeatureMatrix:
    symbol = str(bars["symbol"].iloc[0])

    feature_columns = [
        col for col in bars.columns if col not in {"timestamp_ms", "symbol"}
    ]
    features: Dict[str, Dict[str, list[float]]] = {
        symbol: {
            col: bars[col].astype(float).to_list() for col in feature_columns
        }
    }

    return FeatureMatrix(
        timestamp_ms=bars["timestamp_ms"].astype(int).to_list(),
        features_by_symbol=features,
    )
