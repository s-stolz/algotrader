"""Risk transforms for execution targets."""

from __future__ import annotations

from typing import Dict

import numpy as np
from domain.types import ExecutionArrayBundle


def long_only_rule(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
    """Clamp target quantities at zero to enforce long-only exposure."""

    expected_len = len(bundle.timestamp_ms)
    clamped: Dict[str, list[float]] = {}
    for symbol, values in bundle.target_quantity_by_symbol.items():
        arr = np.asarray(values, dtype=np.float64)
        if arr.size != expected_len:
            raise ValueError(
                f"Target quantity length for symbol {symbol} must match timestamp length"
            )
        clamped[symbol] = np.maximum(arr, 0.0).tolist()

    return ExecutionArrayBundle(
        timestamp_ms=bundle.timestamp_ms,
        target_quantity_by_symbol=clamped,
    )
