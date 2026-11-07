"""Dual evaluation contract for close-time order strategies.

Array builders receive only strategy-resolution features. Sequential builders
receive the previous and current completed snapshots. Both return commands whose
effective timestamps identify completed strategy-candle boundaries.
"""

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from domain.orders import OrderCommand
from domain.types import FeatureMatrix

OrderArrayBuilder = Callable[[FeatureMatrix, Sequence[int]], Sequence[OrderCommand]]
OrderDecision = Callable[
    [int, Mapping[str, float] | None, Mapping[str, float]], Sequence[OrderCommand]
]


@dataclass(frozen=True)
class OrderStrategyModel:
    build_commands: OrderArrayBuilder
    evaluate_close: OrderDecision
