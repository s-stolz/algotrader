"""Validated application registrations, separate from numerical registry plugins."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .core.registry import Indicator, IndicatorRegistry
from .core.spec import IndicatorSpec


@dataclass(frozen=True)
class IndicatorRegistration:
    """One public identity, implementation, live policy and chart presentation."""

    public_id: int
    implementation: type[Indicator]
    supports_live: bool
    overlay: bool
    outputs: dict[str, dict[str, Any]]

    engine_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.implementation, type):
            raise ValueError("Indicator implementation must be a class")
        indicator = self.implementation()
        spec = getattr(indicator, "spec", None)
        if not isinstance(spec, IndicatorSpec) or not isinstance(spec.id, str) or not spec.id:
            raise ValueError("Indicator implementation must declare a nonempty engine ID")
        if any(
            not callable(getattr(indicator, method, None))
            for method in ("batch", "batch_vectorized", "init_state", "update")
        ):
            raise ValueError("Indicator implementation must implement the engine protocol")
        object.__setattr__(self, "engine_id", spec.id)
        if type(self.public_id) is not int or self.public_id <= 0:
            raise ValueError("Public indicator ID must be a positive integer")
        if type(self.supports_live) is not bool or type(self.overlay) is not bool:
            raise ValueError("Live support and overlay must be explicit booleans")
        if not isinstance(self.outputs, dict) or not set(self.outputs).issubset(spec.outputs):
            raise ValueError("Presentation outputs must belong to the indicator specification")
        for metadata in self.outputs.values():
            if not isinstance(metadata, dict) or not isinstance(metadata.get("type"), str):
                raise ValueError("Output presentation must declare a renderer type")
            if not metadata["type"] or not isinstance(metadata.get("plotOptions", {}), dict):
                raise ValueError("Output presentation requires a renderer and valid plot options")
        object.__setattr__(self, "outputs", deepcopy(self.outputs))


class IndicatorCatalog:
    """Validate application registrations and build their computational registry.

    Registration order is public catalog order. Numeric identities are explicit;
    optional computational plugins never become public registrations implicitly.
    """

    def __init__(self, registrations: Iterable[IndicatorRegistration]) -> None:
        self._registrations: dict[int, IndicatorRegistration] = {}
        engine_ids: set[str] = set()
        for registration in registrations:
            if registration.public_id in self._registrations:
                raise ValueError(f"Duplicate public indicator ID: {registration.public_id}")
            if registration.engine_id in engine_ids:
                raise ValueError(f"Duplicate engine indicator ID: {registration.engine_id}")
            self._registrations[registration.public_id] = registration
            engine_ids.add(registration.engine_id)

    def __iter__(self) -> Iterator[IndicatorRegistration]:
        return iter(self._registrations.values())

    def get(self, public_id: int) -> IndicatorRegistration:
        return self._registrations[public_id]

    def create_registry(self) -> IndicatorRegistry:
        """Create independent implementations without discovering external plugins."""
        registry = IndicatorRegistry()
        for entry in self:
            indicator = entry.implementation()
            if indicator.spec.id != entry.engine_id:
                raise ValueError("Indicator implementation changed its registered engine ID")
            registry.register(indicator)
        return registry
