"""Crossing-triggered, flat-only range limits with fill-relative protection."""

import math
from typing import Annotated, Mapping, Sequence

import numpy as np
from domain.enums import OrderSide
from domain.orders import LimitOrder, OrderAction, OrderCommand, OrderProtection
from domain.types import FeatureMatrix

from strategies.base import BarStrategyModel, IndicatorFeatureRequirement, StrategyDefinition
from strategies.orders import OrderStrategyModel
from strategies.registry import ParameterInfo, register_strategy, reject_combination


def _validate_thresholds(parameters: Mapping[str, object]) -> None:
    lower, upper = parameters["rsi_lower"], parameters["rsi_upper"]
    if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower >= upper:
        reject_combination(
            "rsi_lower", "rsi_upper", message="Lower RSI threshold must be below upper threshold"
        )


@register_strategy(
    "rsi_range_limit",
    3,
    display_name="RSI Range Limit",
    execution_mode="orders",
    validator=_validate_thresholds,
)
def build_rsi_range_limit(  # noqa: C901
    *,
    rsi_period: Annotated[int, ParameterInfo(minimum=1)] = 14,
    rsi_lower: Annotated[
        float, ParameterInfo(minimum=0, maximum=100, exclusive_minimum=True, exclusive_maximum=True)
    ] = 30.0,
    rsi_upper: Annotated[
        float, ParameterInfo(minimum=0, maximum=100, exclusive_minimum=True, exclusive_maximum=True)
    ] = 70.0,
    range_period: Annotated[int, ParameterInfo(minimum=1, maximum=5000)] = 20,
    limit_offset_ticks: Annotated[
        int,
        ParameterInfo(
            minimum=0,
            display_name="Limit offset (ticks)",
            description=(
                "Buy below the rolling low; sell above the rolling high. "
                "Uses the selected market’s minimum price increment."
            ),
        ),
    ] = 0,
    quantity: Annotated[float, ParameterInfo(minimum=0, exclusive_minimum=True)] = 1.0,
    lifetime_bars: Annotated[
        int,
        ParameterInfo(minimum=1, description="Pending lifetime in strategy timeframe intervals."),
    ] = 10,
    stop_loss_ticks: Annotated[int, ParameterInfo(minimum=1)] = 100,
    take_profit_ticks: Annotated[int, ParameterInfo(minimum=1)] = 200,
) -> StrategyDefinition:
    """Buy a low-RSI cross at the trailing low; sell a high-RSI cross at the high.

    A tick offset moves buys below the low and sells above the high.
    The closed signal candle belongs to the window. Prices remain frozen, a new
    crossing replaces a pending entry, and signals while positioned are ignored.
    Only protection exits positions; remaining beyond a threshold never resubmits.
    """
    for value in (rsi_period, range_period, lifetime_bars, stop_loss_ticks, take_profit_ticks):
        if type(value) is not int or value < 1:
            raise ValueError("Periods and tick distances must be positive integers")
    if type(limit_offset_ticks) is not int or limit_offset_ticks < 0:
        raise ValueError("limit_offset_ticks must be a nonnegative integer")
    if range_period > 5000:
        raise ValueError("range_period must be at most 5000")
    if not 0 < rsi_lower < rsi_upper < 100:
        raise ValueError("RSI thresholds must satisfy 0 < lower < upper < 100")
    for value in (quantity,):
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError("Quantity must be positive and finite")
    protection = OrderProtection(
        stop_loss_ticks=stop_loss_ticks,
        take_profit_ticks=take_profit_ticks,
    )

    def command(boundary: int, side: OrderSide, price: float) -> OrderCommand:
        identity = f"rsi-range:{boundary}"
        return OrderCommand(
            boundary,
            OrderAction.SUBMIT,
            identity,
            LimitOrder(
                identity,
                side,
                price,
                quantity,
                protection=protection,
                only_when_flat=True,
                replace_group="rsi-range-entry",
                lifetime_bars=lifetime_bars,
                price_offset_ticks=limit_offset_ticks,
            ),
        )

    def arrays(features: FeatureMatrix, boundaries: Sequence[int]) -> list[OrderCommand]:
        values = next(iter(features.features_by_symbol.values()))
        rsi = np.asarray(values["rsi"], dtype=float)
        lows = np.asarray(values["lowest_low"], dtype=float)
        highs = np.asarray(values["highest_high"], dtype=float)
        buy = (rsi[:-1] >= rsi_lower) & (rsi[1:] < rsi_lower)
        sell = (rsi[:-1] <= rsi_upper) & (rsi[1:] > rsi_upper)
        indices = np.flatnonzero(buy | sell) + 1
        return [
            command(
                int(boundaries[int(i)]),
                OrderSide.BUY if buy[i - 1] else OrderSide.SELL,
                float(lows[i] if buy[i - 1] else highs[i]),
            )
            for i in indices
        ]

    def sequential(
        boundary: int, previous: Mapping[str, float] | None, current: Mapping[str, float]
    ) -> list[OrderCommand]:
        if previous is None:
            return []
        if previous["rsi"] >= rsi_lower and current["rsi"] < rsi_lower:
            return [command(boundary, OrderSide.BUY, current["lowest_low"])]
        if previous["rsi"] <= rsi_upper and current["rsi"] > rsi_upper:
            return [command(boundary, OrderSide.SELL, current["highest_high"])]
        return []

    requirements = (
        IndicatorFeatureRequirement("rsi", "rsi", "rsi", {"length": rsi_period, "source": "close"}),
        IndicatorFeatureRequirement(
            "highest_high", "rolling_range", "highest_high", {"window": range_period}
        ),
        IndicatorFeatureRequirement(
            "lowest_low", "rolling_range", "lowest_low", {"window": range_period}
        ),
    )
    empty = BarStrategyModel((), (), quantity)
    return StrategyDefinition(
        strategy_id="rsi_range_limit",
        feature_specs=("rsi", "highest_high", "lowest_low"),
        decision_model=empty.build_signals,
        position_builder=empty.build_positions,
        indicator_requirements=requirements,
        order_model=OrderStrategyModel(arrays, sequential, requires_min_move=True),
        metadata={"warmup_bars": max(rsi_period + 1, range_period)},
    )
