"""Reference SMA crossover strategy for vectorized bar backtests."""

from __future__ import annotations

from execution.risk import long_only_rule
from execution.sizing import fixed_quantity_sizer

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
) -> StrategyDefinition:
    """Build a long-only SMA crossover strategy definition."""

    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("SMA windows must be positive integers")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be strictly smaller than slow_window")
    if quantity <= 0.0:
        raise ValueError("quantity must be positive")

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
        long_only=True,
        protective_exit=ProtectiveExitSpec(stop_loss_pct=stop_loss_pct),
    )

    return StrategyDefinition(
        strategy_id="sma_crossover",
        feature_specs=("sma_fast", "sma_slow"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        indicator_requirements=indicator_requirements,
        bar_model=bar_model,
        sizing_model=fixed_quantity_sizer(quantity),
        risk_rules=(long_only_rule,),
        metadata={
            "warmup_bars": slow_window,
        },
    )
