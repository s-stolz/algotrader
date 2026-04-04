"""Indicator registry with optional entry point discovery."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, Dict, Iterable, Protocol, Tuple, Union

import numpy as np

from .results import IndicatorResult
from .spec import IndicatorSpec
from .tensor import Tensor


class Indicator(Protocol):
    """Protocol for indicator implementations registered in the engine."""

    spec: IndicatorSpec

    def batch(self, *args, **kwargs) -> Union[Tensor, IndicatorResult]: ...

    def batch_vectorized(self, *args, **kwargs) -> Tensor: ...

    def init_state(self, *args, **kwargs) -> Any: ...

    def update(self, *args, **kwargs) -> Tuple[Any, Union[Tensor, np.ndarray]]: ...


@dataclass
class RegistryEntry:
    indicator: Indicator


class IndicatorRegistry:
    """Registry for indicator implementations."""

    def __init__(self) -> None:
        self._entries: Dict[str, RegistryEntry] = {}

    def register(self, indicator: Indicator) -> None:
        """Register a single indicator instance."""
        indicator_id = indicator.spec.id
        if indicator_id in self._entries:
            raise ValueError(f"Indicator already registered: {indicator_id}")
        self._entries[indicator_id] = RegistryEntry(indicator=indicator)

    def register_many(self, indicators: Iterable[Indicator]) -> None:
        """Register multiple indicators."""
        for indicator in indicators:
            self.register(indicator)

    def get(self, indicator_id: str) -> Indicator:
        """Return the indicator implementation for a given id."""
        if indicator_id not in self._entries:
            raise KeyError(f"Indicator not found: {indicator_id}")
        return self._entries[indicator_id].indicator

    def list_specs(self) -> Dict[str, IndicatorSpec]:
        """Return a mapping of indicator id to spec."""
        return {key: entry.indicator.spec for key, entry in self._entries.items()}

    def load_entry_points(self, group: str = "indicator_engine.indicators") -> None:
        """Load and register indicators exposed via Python entry points."""
        eps = entry_points()
        for ep in eps.select(group=group):
            loaded = ep.load()
            indicator = loaded() if isinstance(loaded, type) else loaded
            self.register(indicator)
