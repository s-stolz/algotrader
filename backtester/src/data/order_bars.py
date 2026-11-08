"""Validated strategy and minute clocks for order execution."""

from dataclasses import replace

import numpy as np
import pandas as pd
from db_accessor_client.timeframes import timeframe_to_minutes
from domain.orders import OrderCommand
from domain.types import BacktestRequest, FeatureMatrix

from data.normalization import normalize_bar_data


def close_timestamps(bars: pd.DataFrame, timeframe: str) -> list[int]:
    timestamps = bars["timestamp_ms"].to_numpy(dtype="int64")
    if timeframe.upper() == "MN1":
        return [
            int(
                (pd.Timestamp(int(value), unit="ms", tz="UTC") + pd.DateOffset(months=1)).value
                // 1_000_000
            )
            for value in timestamps
        ]
    duration = timeframe_to_minutes(timeframe) * 60_000
    return (timestamps + duration).tolist()


def minute_bars(request: BacktestRequest, bars: pd.DataFrame) -> pd.DataFrame:
    raw = bars.copy()
    if "symbol" in raw:
        raw = raw.loc[raw["symbol"] == request.symbols[0]]
    times = np.asarray(pd.to_numeric(raw["timestamp_ms"], errors="raise"), dtype=np.float64)
    if not np.isfinite(times).all() or np.any(times % 60_000) or len(set(times)) != len(times):
        raise ValueError("Minute execution candles require unique integer minute timestamps")
    normalized = normalize_bar_data(bars=raw, symbol=request.symbols[0])
    result = normalized.loc[
        (normalized.timestamp_ms >= request.start_ms) & (normalized.timestamp_ms < request.end_ms)
    ].reset_index(drop=True)
    if result.empty:
        raise ValueError("No minute execution candles in requested interval")
    return result


def feature_matrix(bars: pd.DataFrame, symbol: str) -> FeatureMatrix:
    return FeatureMatrix(
        timestamp_ms=bars.timestamp_ms.astype(int).tolist(),
        features_by_symbol={
            symbol: {
                column: bars[column].astype(float).tolist()
                for column in bars
                if column not in ("timestamp_ms", "symbol")
            }
        },
    )


def resolve_order_expiry(command: OrderCommand, timeframe: str) -> OrderCommand:
    """Resolve a candle-duration lifetime without reading future candles."""
    order = command.order
    if order is None or order.lifetime_bars is None:
        return command
    if timeframe.upper() == "MN1":
        expiry = int(
            (
                pd.Timestamp(command.effective_at_ms, unit="ms", tz="UTC")
                + pd.DateOffset(months=order.lifetime_bars)
            ).value
            // 1_000_000
        )
    else:
        expiry = (
            command.effective_at_ms + order.lifetime_bars * timeframe_to_minutes(timeframe) * 60_000
        )
    return replace(command, order=replace(order, expires_at_ms=expiry, lifetime_bars=None))


def resolve_order_ticks(command: OrderCommand, min_move: float | None) -> OrderCommand:
    """Convert tick distances using the accepted run's immutable Market metadata."""
    if command.protection is not None:
        return replace(command, protection=command.protection.resolve_ticks(min_move))
    if command.order is not None:
        return replace(command, order=command.order.resolve_ticks(min_move))
    return command
