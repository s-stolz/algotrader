"""Saved reporting metric validation."""

import math
from typing import Any, Mapping


def validate_profit_factor(metrics: Mapping[str, Any]) -> None:
    """Require the saved JSON union without coercing missing or invalid values."""
    if "profit_factor" not in metrics:
        raise ValueError("metrics.profit_factor is required")
    value = metrics["profit_factor"]
    if value is None or value == "infinity":
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "metrics.profit_factor must be a nonnegative finite number, infinity, or null"
        )
    if not math.isfinite(value) or value < 0:
        raise ValueError(
            "metrics.profit_factor must be a nonnegative finite number, infinity, or null"
        )
