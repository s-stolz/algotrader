"""Exact equity reconstruction from immutable fills and identified Candle closes."""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any, Mapping, Sequence

import pandas as pd
from domain.enums import DataGranularity, OrderSide
from domain.types import BacktestFillRecord, BacktestRequest

ALGORITHM = "sha256-ts-close-v1"
DOMAIN_MARKER = b"algotrader/equity-replay/sha256-ts-close-v1\x00"


class ReplayUnavailableError(ValueError):
    """Saved data cannot produce an exact curve."""


def executable_closes(
    bars: pd.DataFrame, *, first_timestamp_ms: int | None = None
) -> list[tuple[int, float]]:
    if "timestamp_ms" not in bars or "close" not in bars:
        raise ReplayUnavailableError("unsupported_replay_shape")
    closes: list[tuple[int, float]] = []
    previous: int | None = None
    for timestamp, close in zip(
        bars["timestamp_ms"].to_numpy(), bars["close"].to_numpy(), strict=True
    ):
        if (
            isinstance(timestamp, bool)
            or int(timestamp) != timestamp
            or not -(2**63) <= int(timestamp) < 2**63
        ):
            raise ReplayUnavailableError("unsupported_replay_shape")
        timestamp = int(timestamp)
        if first_timestamp_ms is not None and timestamp < first_timestamp_ms:
            continue
        close = float(close)
        if not math.isfinite(close) or (previous is not None and timestamp <= previous):
            raise ReplayUnavailableError("unsupported_replay_shape")
        closes.append((timestamp, close))
        previous = timestamp
    if not closes:
        raise ReplayUnavailableError("unsupported_replay_shape")
    return closes


def descriptor(request: BacktestRequest, closes: Sequence[tuple[int, float]]) -> dict[str, Any]:
    if len(request.symbols) != 1 or request.data_granularity != DataGranularity.BAR or not closes:
        raise ReplayUnavailableError("unsupported_replay_shape")
    digest = hashlib.sha256()
    digest.update(DOMAIN_MARKER)
    for identity in (request.exchange or "", str(request.symbols[0]), request.timeframe):
        encoded = identity.encode("utf-8")
        digest.update(struct.pack(">I", len(encoded)))
        digest.update(encoded)
    previous: int | None = None
    for timestamp, close in closes:
        if (previous is not None and timestamp <= previous) or not math.isfinite(close):
            raise ReplayUnavailableError("unsupported_replay_shape")
        digest.update(struct.pack(">q", timestamp))
        digest.update(struct.pack(">d", 0.0 if close == 0.0 else close))
        previous = timestamp
    return {
        "schema_version": 1,
        "fingerprint_algorithm": ALGORITHM,
        "fingerprint_digest": digest.hexdigest(),
        "source_point_count": len(closes),
        "first_timestamp_ms": closes[0][0],
        "last_timestamp_ms": closes[-1][0],
    }


def valid_descriptor(value: Mapping[str, Any]) -> bool:
    digest = value.get("fingerprint_digest")
    count = value.get("source_point_count")
    first = value.get("first_timestamp_ms")
    last = value.get("last_timestamp_ms")
    return (
        value.get("schema_version") == 1
        and value.get("fingerprint_algorithm") == ALGORITHM
        and isinstance(digest, str)
        and len(digest) == 64
        and all(char in "0123456789abcdef" for char in digest)
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count > 0
        and isinstance(first, int)
        and isinstance(last, int)
        and first <= last
        and (count == 1 or first < last)
    )


def replay(
    request: BacktestRequest,
    saved_descriptor: Mapping[str, Any],
    closes: Sequence[tuple[int, float]],
    fills: Sequence[BacktestFillRecord],
) -> list[dict[str, float | int]]:
    try:
        expected = descriptor(request, closes)
    except (ValueError, OverflowError, struct.error) as exc:
        raise ReplayUnavailableError("unsupported_replay_shape") from exc
    if dict(saved_descriptor) != expected:
        raise ReplayUnavailableError("fingerprint_mismatch")
    cash = float(request.initial_capital)
    if not math.isfinite(cash) or cash <= 0:
        raise ReplayUnavailableError("unsupported_replay_shape")
    quantity = 0.0
    fill_index = 0
    points: list[dict[str, float | int]] = []
    peak = -math.inf
    for timestamp, close in closes:
        while fill_index < len(fills) and fills[fill_index].timestamp_ms == timestamp:
            fill = fills[fill_index]
            cash, quantity = _apply_fill(fill, fill_index, request.symbols[0], cash, quantity)
            fill_index += 1
        if fill_index < len(fills) and fills[fill_index].timestamp_ms < timestamp:
            raise ReplayUnavailableError("unsupported_replay_shape")
        equity = cash + quantity * close
        if not math.isfinite(equity):
            raise ReplayUnavailableError("unsupported_replay_shape")
        peak = max(peak, equity)
        drawdown = min(0.0, ((equity - peak) / peak) * 100.0) if peak > 0 else 0.0
        points.append({"timestamp_ms": timestamp, "equity": equity, "drawdown_pct": drawdown})
    if fill_index != len(fills):
        raise ReplayUnavailableError("unsupported_replay_shape")
    return points


def sample(
    points: Sequence[dict[str, float | int]], max_points: int
) -> list[dict[str, float | int]]:
    if len(points) <= max_points:
        return list(points)
    peak_index = max_peak_index = trough_index = 0
    worst = 0.0
    for index, point in enumerate(points):
        if point["equity"] > points[peak_index]["equity"]:
            peak_index = index
        if point["drawdown_pct"] < worst:
            worst = float(point["drawdown_pct"])
            max_peak_index, trough_index = peak_index, index
    anchors = {0, len(points) - 1, max_peak_index, trough_index}
    retained = set(anchors)
    candidates = [index for index in range(len(points)) if index not in anchors]
    capacity = max_points - len(retained)
    bucket_count = capacity // 2
    for bucket in range(bucket_count):
        group = candidates[
            bucket
            * len(candidates)
            // bucket_count : (bucket + 1)
            * len(candidates)
            // bucket_count
        ]
        if group:
            retained.add(min(group, key=lambda index: (points[index]["equity"], index)))
            retained.add(max(group, key=lambda index: (points[index]["equity"], -index)))
    return [points[index] for index in sorted(retained)]


def _apply_fill(
    fill: BacktestFillRecord,
    sequence: int,
    symbol: str,
    cash: float,
    quantity: float,
) -> tuple[float, float]:
    if (
        fill.sequence != sequence
        or fill.symbol != symbol
        or fill.side not in (OrderSide.BUY, OrderSide.SELL)
    ):
        raise ReplayUnavailableError("unsupported_replay_shape")
    if not all(math.isfinite(value) for value in (fill.quantity, fill.price, fill.fees)) or (
        fill.quantity <= 0 or fill.price <= 0 or fill.fees < 0
    ):
        raise ReplayUnavailableError("unsupported_replay_shape")
    signed = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
    cash -= signed * fill.price + fill.fees
    quantity += signed
    if not math.isfinite(cash) or not math.isfinite(quantity):
        raise ReplayUnavailableError("unsupported_replay_shape")
    return cash, quantity
