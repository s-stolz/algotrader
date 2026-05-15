"""Sizing transforms for execution targets."""

from __future__ import annotations

from typing import Dict

import numpy as np
from domain.types import ExecutionArrayBundle


def fixed_quantity_sizer(quantity: float):
    """Return a sizing transform that maps any positive target to `quantity`."""

    def _transform(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
        expected_len = len(bundle.timestamp_ms)
        scaled: Dict[str, list[float]] = {}
        for symbol, values in bundle.target_quantity_by_symbol.items():
            arr = np.asarray(values, dtype=np.float64)
            if arr.size != expected_len:
                raise ValueError(
                    f"Target quantity length for symbol {symbol} must match timestamp length"
                )
            out = np.where(arr > 0.0, float(quantity), 0.0)
            scaled[symbol] = out.tolist()
        return ExecutionArrayBundle(
            timestamp_ms=bundle.timestamp_ms,
            target_quantity_by_symbol=scaled,
        )

    return _transform
