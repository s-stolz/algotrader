"""Utility functions for the ingestion service."""
from datetime import datetime, timezone
from typing import Union


def iso_to_epoch_ms(timestamp: str) -> int:
    """Convert ISO format timestamp to epoch milliseconds.

    Args:
        timestamp: ISO format string (e.g., "2025-01-01T00:00:00Z")

    Returns:
        Epoch milliseconds as integer
    """
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def epoch_ms_to_iso(timestamp_ms: int) -> str:
    """Convert epoch milliseconds to ISO format string.

    Args:
        timestamp_ms: Epoch milliseconds

    Returns:
        ISO format string (YYYY-MM-DD HH:MM:SS)
    """
    timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')


def normalize_timestamp_to_epoch_ms(timestamp: Union[str, int]) -> int:
    """Normalize timestamp to epoch milliseconds.

    Handles both ISO format strings and epoch milliseconds.

    Args:
        timestamp: Either ISO format string or epoch milliseconds

    Returns:
        Epoch milliseconds as integer
    """
    if isinstance(timestamp, str) and "T" in timestamp:
        return iso_to_epoch_ms(timestamp)
    return int(timestamp)
