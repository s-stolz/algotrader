"""Risk transforms for execution targets."""

from __future__ import annotations

from typing import Dict

import numpy as np
from domain.types import ExecutionArrayBundle


def long_only_rule(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
    """Clamp target quantities at zero to enforce long-only exposure."""

    clamped: Dict[str, list[float]] = {}
    for symbol, values in bundle.target_quantity_by_symbol.items():
        arr = np.asarray(values, dtype=np.float64)
        clamped[symbol] = np.maximum(arr, 0.0).tolist()

    return ExecutionArrayBundle(
        timestamp_ms=bundle.timestamp_ms,
        target_quantity_by_symbol=clamped,
    )
