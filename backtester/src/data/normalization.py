"""Market-data normalization for bar-mode backtests."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

REQUIRED_BAR_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp_ms",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


def normalize_bar_data(
    *,
    bars: pd.DataFrame,
    symbol: str,
) -> pd.DataFrame:
    """Normalize raw bars into deterministic canonical schema and ordering."""

    normalized = bars.copy()

    if "symbol" not in normalized.columns:
        normalized["symbol"] = symbol

    normalized["symbol"] = normalized["symbol"].astype(str)
    normalized = normalized.loc[normalized["symbol"] == symbol].copy()
    if normalized.empty:
        raise ValueError(f"No bars found for symbol {symbol}")

    missing = [column for column in REQUIRED_BAR_COLUMNS if column not in normalized.columns]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"bars is missing required columns: {missing_text}")

    normalized = normalized.loc[:, list(REQUIRED_BAR_COLUMNS)].copy()

    numeric_columns = ("timestamp_ms", "open", "high", "low", "close", "volume")
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized[column] = normalized[column].replace([np.inf, -np.inf], np.nan)

    normalized.dropna(subset=list(numeric_columns), inplace=True)
    if normalized.empty:
        raise ValueError(f"No valid numeric bars found for symbol {symbol}")

    normalized["timestamp_ms"] = normalized["timestamp_ms"].astype("int64")
    for column in ("open", "high", "low", "close", "volume"):
        normalized[column] = normalized[column].astype("float64")

    normalized.sort_values(by="timestamp_ms", kind="mergesort", inplace=True)
    normalized.drop_duplicates(subset=["timestamp_ms", "symbol"], keep="last", inplace=True)
    normalized.reset_index(drop=True, inplace=True)
    return normalized
