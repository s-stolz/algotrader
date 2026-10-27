"""MACD signal-line crossovers confirmed by a closing-price EMA filter."""

from __future__ import annotations

import math
from typing import Annotated, Mapping

from strategies.base import (
    BarStrategyModel,
    IndicatorFeatureRequirement,
    ProtectiveExitSpec,
    StrategyDefinition,
)
from strategies.conditions import ConditionRule
from strategies.registry import ParameterInfo, register_strategy, reject_combination


def _validate_macd_parameters(parameters: Mapping[str, object]) -> None:
    fast = parameters["fast_window"]
    slow = parameters["slow_window"]
    if isinstance(fast, int) and isinstance(slow, int) and fast >= slow:
        reject_combination(
            "fast_window",
            "slow_window",
            message="Fast window must be smaller than slow window",
        )


@register_strategy(
    "macd_ema",
    1,
    display_name="MACD crossover with EMA filter",
    validator=_validate_macd_parameters,
)
def build_macd_ema_strategy(
    *,
    fast_window: Annotated[int, ParameterInfo(minimum=1)] = 12,
    slow_window: Annotated[int, ParameterInfo(minimum=1)] = 26,
    signal_window: Annotated[int, ParameterInfo(minimum=1)] = 9,
    ema_window: Annotated[int, ParameterInfo(minimum=1)] = 200,
    quantity: Annotated[float, ParameterInfo(minimum=0.0, exclusive_minimum=True)] = 1.0,
    stop_loss_pct: Annotated[
        float | None,
        ParameterInfo(minimum=0.0, maximum=100.0, exclusive_minimum=True, exclusive_maximum=True),
    ] = None,
    take_profit_pct: Annotated[
        float | None, ParameterInfo(minimum=0.0, exclusive_minimum=True)
    ] = None,
) -> StrategyDefinition:
    """Hold until a qualifying opposite crossover or a configured protective exit."""
    for name, window in (
        ("fast_window", fast_window),
        ("slow_window", slow_window),
        ("signal_window", signal_window),
        ("ema_window", ema_window),
    ):
        if type(window) is not int or window <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be strictly smaller than slow_window")
    if (
        not isinstance(quantity, (int, float))
        or isinstance(quantity, bool)
        or not math.isfinite(float(quantity))
        or quantity <= 0.0
    ):
        raise ValueError("quantity must be positive and finite")

    macd_parameters = {
        "fast": fast_window,
        "slow": slow_window,
        "signal": signal_window,
        "source": "close",
    }
    requirements = (
        IndicatorFeatureRequirement("macd", "macd", "macd", macd_parameters),
        IndicatorFeatureRequirement("macd_signal", "macd", "signal", macd_parameters),
        IndicatorFeatureRequirement("ema", "ema", "ema", {"window": ema_window, "source": "close"}),
    )
    bar_model = BarStrategyModel(
        entry_conditions=(ConditionRule.crossover("macd", "macd_signal"),),
        exit_conditions=(ConditionRule.crossunder("macd", "macd_signal"),),
        entry_filters=(ConditionRule.above("close", "ema"),),
        exit_filters=(ConditionRule.below("close", "ema"),),
        target_quantity=quantity,
        protective_exit=ProtectiveExitSpec(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        ),
    )
    return StrategyDefinition(
        strategy_id="macd_ema",
        feature_specs=("close", "macd", "macd_signal", "ema"),
        decision_model=bar_model.build_signals,
        position_builder=bar_model.build_positions,
        indicator_requirements=requirements,
        bar_model=bar_model,
        metadata={"warmup_bars": max(ema_window, slow_window + signal_window)},
    )
