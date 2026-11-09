"""Two-sided, expiring OCO limits with partial profit taking."""

from typing import Annotated, Mapping, Sequence

import numpy as np
from domain.enums import OrderSide
from domain.orders import LimitOrder, OrderAction, OrderCommand, OrderProtection, TakeProfitTier
from domain.types import FeatureMatrix

from strategies.base import BarStrategyModel, StrategyDefinition
from strategies.orders import OrderStrategyModel
from strategies.registry import ParameterInfo, register_strategy


@register_strategy("limit_reversion", 1, display_name="Limit reversion", execution_mode="orders")
def build_limit_reversion(
    *,
    offset_pct: Annotated[
        float, ParameterInfo(minimum=0, maximum=100, exclusive_minimum=True, exclusive_maximum=True)
    ] = 1.0,
    quantity: Annotated[float, ParameterInfo(minimum=0, exclusive_minimum=True)] = 1.0,
    lifetime_minutes: Annotated[int, ParameterInfo(minimum=1)] = 10,
    stop_pct: Annotated[
        float, ParameterInfo(minimum=0, maximum=100, exclusive_minimum=True, exclusive_maximum=True)
    ] = 2.0,
    profit_pct: Annotated[
        float, ParameterInfo(minimum=0, maximum=50, exclusive_minimum=True, exclusive_maximum=True)
    ] = 1.0,
) -> StrategyDefinition:
    def commands(boundary: int, buy: float, sell: float) -> list[OrderCommand]:
        result = []
        group = f"entry:{boundary}"
        for side, price, direction in ((OrderSide.BUY, buy, 1), (OrderSide.SELL, sell, -1)):
            identity = f"{group}:{side.value}"
            protection = OrderProtection(
                stop_price=price * (1 - direction * stop_pct / 100),
                take_profits=(
                    TakeProfitTier(price * (1 + direction * profit_pct / 100), fraction=0.5),
                    TakeProfitTier(price * (1 + direction * profit_pct / 50), fraction=0.5),
                ),
            )
            order = LimitOrder(
                identity,
                side,
                float(price),
                quantity,
                expires_at_ms=boundary + lifetime_minutes * 60_000,
                oco_group=group,
                protection=protection,
            )
            result.append(OrderCommand(boundary, OrderAction.SUBMIT, identity, order))
        return result

    def arrays(features: FeatureMatrix, boundaries: Sequence[int]) -> list[OrderCommand]:
        values = np.asarray(next(iter(features.features_by_symbol.values()))["close"], dtype=float)
        buy, sell = values * (1 - offset_pct / 100), values * (1 + offset_pct / 100)
        return [
            command
            for boundary, low, high in zip(boundaries, buy, sell, strict=True)
            for command in commands(int(boundary), float(low), float(high))
        ]

    def sequential(
        boundary: int, previous: Mapping[str, float] | None, current: Mapping[str, float]
    ) -> list[OrderCommand]:
        return commands(
            boundary,
            current["close"] * (1 - offset_pct / 100),
            current["close"] * (1 + offset_pct / 100),
        )

    empty = BarStrategyModel((), (), quantity)
    return StrategyDefinition(
        strategy_id="limit_reversion",
        feature_specs=("close",),
        decision_model=empty.build_signals,
        position_builder=empty.build_positions,
        order_model=OrderStrategyModel(arrays, sequential),
    )
