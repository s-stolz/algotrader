"""Canonical timeframe codes and conversion helpers."""

from __future__ import annotations

from typing import Final

TIMEFRAME_TO_MINUTES: Final[dict[str, int]] = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "H12": 720,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}

def normalize_timeframe_code(timeframe: str) -> str:
    """Normalize a timeframe input to broker/cTrader code format."""
    normalized = timeframe.upper()
    if normalized not in TIMEFRAME_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe code: {timeframe}")
    return normalized


def timeframe_to_minutes(timeframe: str) -> int:
    """Convert a timeframe code to minutes."""
    code = normalize_timeframe_code(timeframe)
    return TIMEFRAME_TO_MINUTES[code]
