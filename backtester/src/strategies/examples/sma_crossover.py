"""Reference SMA crossover strategy for vectorized bar backtests."""

from __future__ import annotations

import math

from strategies.base import (
    BarStrategyModel,
    IndicatorFeatureRequirement,
    ProtectiveExitSpec,
    StrategyDefinition,
)
from strategies.conditions import ConditionRule


def build_sma_crossover_strategy(
    *,
    fast_window: int = 5,
    slow_window: int = 20,
    quantity: float = 1.0,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> StrategyDefinition:
    """Build a direction-neutral SMA crossover strategy definition."""

    if (
        not isinstance(fast_window, int)
        or isinstance(fast_window, bool)
        or not isinstance(slow_window, int)
        or isinstance(slow_window, bool)
    ):
        raise ValueError("SMA windows must be integers")
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("SMA windows must be positive integers")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be strictly smaller than slow_window")
    if (
        not isinstance(quantity, (int, float))
        or isinstance(quantity, bool)
        or not math.isfinite(float(quantity))
        or quantity <= 0.0
    ):
        raise ValueError("quantity must be positive and finite")

    indicator_requirements = (
        IndicatorFeatureRequirement(
            feature_name="sma_fast",
            indicator_id="sma",
            output_key="sma",
            parameters={"window": fast_window, "source": "close"},
        ),
        IndicatorFeatureRequirement(
            feature_name="sma_slow",
            indicator_id="sma",
            output_key="sma",
            parameters={"window": slow_window, "source": "close"},
        ),
    )
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.crossover("sma_fast", "sma_slow"),),
        exit_conditions=(ConditionRule.crossunder("sma_fast", "sma_slow"),),
        target_quantity=quantity,
        protective_exit=ProtectiveExitSpec(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        ),
    )

    return StrategyDefinition(
        strategy_id="sma_crossover",
        feature_specs=("sma_fast", "sma_slow"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        indicator_requirements=indicator_requirements,
        bar_model=bar_model,
        metadata={
            "warmup_bars": slow_window,
        },
    )
