"""Resolved indicator configurations for inspecting completed backtests."""

from __future__ import annotations

import json
from typing import Any

from indicator_engine import get_registry

from strategies.base import StrategyDefinition


def snapshot_chart_indicators(strategy: StrategyDefinition) -> dict[str, Any]:
    """Capture each calculation once, including defaults from the executing code."""
    registry = get_registry()
    items = []
    seen = set()
    for requirement in strategy.indicator_requirements:
        spec = registry.get(requirement.indicator_id).spec
        parameters = {
            name: schema["default"]
            for name, schema in spec.parameters.items()
            if "default" in schema
        }
        parameters.update(requirement.parameters)
        item = {"indicator_id": spec.id, "parameters": parameters}
        encoded = json.dumps(item, sort_keys=True, allow_nan=False)
        if encoded not in seen:
            seen.add(encoded)
            items.append(json.loads(encoded))
    return {"schema_version": 1, "items": items}
