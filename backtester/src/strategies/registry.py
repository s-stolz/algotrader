"""Registry for built-in strategy definitions."""

from __future__ import annotations

from typing import Callable

from domain.types import StrategyConfig

from strategies.base import StrategyDefinition
from strategies.examples.sma_crossover import build_sma_crossover_strategy

StrategyBuilder = Callable[..., StrategyDefinition]

_STRATEGY_BUILDERS: dict[str, StrategyBuilder] = {
    "sma_crossover": build_sma_crossover_strategy,
}


def resolve_strategy(config: StrategyConfig) -> StrategyDefinition:
    """Resolve a request strategy config into a concrete strategy definition."""

    builder = _STRATEGY_BUILDERS.get(config.strategy_id)
    if builder is None:
        raise ValueError(f"Unknown strategy_id {config.strategy_id!r}")

    try:
        return builder(**dict(config.parameters))
    except TypeError as exc:
        raise ValueError(f"Invalid parameters for strategy {config.strategy_id!r}: {exc}") from exc
