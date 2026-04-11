"""Reference SMA crossover strategy for vectorized bar backtests."""

from __future__ import annotations

from typing import Dict

import numpy as np
import numpy.typing as npt
import pandas as pd
from domain.types import ExecutionArrayBundle, FeatureMatrix, SignalMatrix
from execution.risk import long_only_rule
from execution.sizing import fixed_quantity_sizer

from strategies.base import StrategyDefinition
from strategies.conditions import crossover, crossunder


def _rolling_mean(values: npt.ArrayLike, window: int) -> npt.NDArray[np.float64]:
    rolling = pd.Series(values, dtype=np.float64).rolling(window=window, min_periods=window).mean()
    return np.asarray(rolling, dtype=np.float64)


def build_sma_crossover_strategy(
    *,
    fast_window: int = 5,
    slow_window: int = 20,
    quantity: float = 1.0,
) -> StrategyDefinition:
    """Build a long-only SMA crossover strategy definition."""

    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("SMA windows must be positive integers")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be strictly smaller than slow_window")
    if quantity <= 0.0:
        raise ValueError("quantity must be positive")

    def decision_model(features: FeatureMatrix) -> SignalMatrix:
        signals_by_symbol: Dict[str, list[int]] = {}

        for symbol, feature_map in features.features_by_symbol.items():
            if "close" not in feature_map:
                raise ValueError(f"Feature 'close' is required for symbol {symbol}")

            close = np.asarray(feature_map["close"], dtype=np.float64)
            sma_fast = _rolling_mean(close, fast_window)
            sma_slow = _rolling_mean(close, slow_window)

            entries = crossover(sma_fast, sma_slow)
            exits = crossunder(sma_fast, sma_slow)

            signal = np.zeros(close.shape[0], dtype=np.int64)
            signal[entries] = 1
            signal[exits] = -1
            signals_by_symbol[symbol] = signal.tolist()

        return SignalMatrix(
            timestamp_ms=features.timestamp_ms,
            signals_by_symbol=signals_by_symbol,
        )

    def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
        target_by_symbol: Dict[str, list[float]] = {}

        for symbol, raw_signals in signals.signals_by_symbol.items():
            signal_arr = np.asarray(raw_signals, dtype=np.int64)
            target = np.full(signal_arr.shape[0], np.nan, dtype=np.float64)
            target[signal_arr > 0] = float(quantity)
            target[signal_arr < 0] = 0.0

            target_series = pd.Series(target, dtype=np.float64).ffill().fillna(0.0)
            target_by_symbol[symbol] = np.asarray(target_series, dtype=np.float64).tolist()

        return ExecutionArrayBundle(
            timestamp_ms=signals.timestamp_ms,
            target_quantity_by_symbol=target_by_symbol,
        )

    return StrategyDefinition(
        strategy_id="sma_crossover",
        feature_specs=("close",),
        decision_model=decision_model,
        position_builder=position_builder,
        sizing_model=fixed_quantity_sizer(quantity),
        risk_rules=(long_only_rule,),
    )
