"""External integration adapters for backtester."""

from .db_accessor import (
    CandleSourceClient,
    DatabaseAccessorHistoricalDataAdapter,
    HistoricalBarDataAdapter,
)

__all__ = [
    "CandleSourceClient",
    "DatabaseAccessorHistoricalDataAdapter",
    "HistoricalBarDataAdapter",
]
