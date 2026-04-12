"""Reference SMA crossover strategy for vectorized bar backtests."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
from domain.types import ExecutionArrayBundle, FeatureMatrix, SignalMatrix
from execution.risk import long_only_rule
from execution.sizing import fixed_quantity_sizer

from strategies.base import StrategyDefinition
from strategies.conditions import crossover, crossunder


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
            missing = [name for name in ("sma_fast", "sma_slow") if name not in feature_map]
            if missing:
                missing_text = ", ".join(missing)
                raise ValueError(
                    f"SMA crossover strategy requires features [{missing_text}] for symbol {symbol}"
                )

            sma_fast = np.asarray(feature_map["sma_fast"], dtype=np.float64)
            sma_slow = np.asarray(feature_map["sma_slow"], dtype=np.float64)

            entries = crossover(sma_fast, sma_slow)
            exits = crossunder(sma_fast, sma_slow)

            signal = np.zeros(sma_fast.shape[0], dtype=np.int64)
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

    indicator_specs: tuple[dict[str, Any], ...] = (
        {
            "indicator_id": "sma",
            "output_key": "sma",
            "output_column": "sma_fast",
            "params": {"window": fast_window, "source": "close"},
        },
        {
            "indicator_id": "sma",
            "output_key": "sma",
            "output_column": "sma_slow",
            "params": {"window": slow_window, "source": "close"},
        },
    )

    return StrategyDefinition(
        strategy_id="sma_crossover",
        feature_specs=("sma_fast", "sma_slow"),
        decision_model=decision_model,
        position_builder=position_builder,
        sizing_model=fixed_quantity_sizer(quantity),
        risk_rules=(long_only_rule,),
        metadata={
            "warmup_bars": slow_window,
            "indicator_specs": indicator_specs,
        },
    )
