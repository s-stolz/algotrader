"""Incremental equity reconstruction; previews become exact only after verification."""

import asyncio
import math
import time
from contextlib import aclosing
from typing import Any, AsyncGenerator, Callable, Mapping, Sequence

from db_accessor_client import AsyncDatabaseAccessorClient
from domain.enums import DataGranularity
from domain.types import BacktestFillRecord, BacktestRequest

from app.equity_replay import (
    ReplayUnavailableError,
    _apply_fill,
    descriptor,
    sample,
    valid_descriptor,
)


class EquityReplayStream:
    def __init__(
        self,
        request: BacktestRequest,
        saved: Mapping[str, Any],
        fills: Sequence[BacktestFillRecord],
        max_points: int,
    ):
        if not 100 <= max_points <= 10000:
            raise ValueError("max_points must be between 100 and 10000")
        self.request, self.saved, self.fills = request, saved, fills
        self.max_points = max_points
        self.cash = float(request.initial_capital)
        self.quantity = 0.0
        self.fill_index = 0
        self.peak = -math.inf
        self.closes: list[tuple[int, float]] = []
        self.points: list[dict[str, float | int]] = []
        self.previous: int | None = None
        self.multiplier = request.instrument.contract_multiplier if request.instrument else 1.0
        if not math.isfinite(self.cash) or self.cash <= 0:
            raise ReplayUnavailableError("unsupported_replay_shape")

    def append(self, candles):
        for candle in candles:
            timestamp, close = candle["timestamp_ms"], float(candle["close"])
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, int)
                or not -(2**63) <= timestamp < 2**63
                or not math.isfinite(close)
                or (self.previous is not None and timestamp <= self.previous)
            ):
                raise ReplayUnavailableError("unsupported_replay_shape")
            if self.request.execution.execution_mode == "orders" and timestamp % 60_000:
                raise ReplayUnavailableError("unsupported_replay_shape")
            self.previous = timestamp
            if timestamp < self.saved["first_timestamp_ms"]:
                continue
            if (
                self.request.execution.sizing is not None
                and timestamp > self.saved["last_timestamp_ms"]
            ):
                continue
            self.closes.append((timestamp, close))
            while (
                self.fill_index < len(self.fills)
                and self.fills[self.fill_index].timestamp_ms == timestamp
            ):
                self.cash, self.quantity = _apply_fill(
                    self.fills[self.fill_index],
                    self.fill_index,
                    self.request.symbols[0],
                    self.cash,
                    self.quantity,
                    self.multiplier,
                )
                self.fill_index += 1
            if (
                self.fill_index < len(self.fills)
                and self.fills[self.fill_index].timestamp_ms < timestamp
            ):
                raise ReplayUnavailableError("unsupported_replay_shape")
            equity = self.cash + self.quantity * close * self.multiplier
            if not math.isfinite(equity):
                raise ReplayUnavailableError("unsupported_replay_shape")
            self.peak = max(self.peak, equity)
            drawdown = (
                min(0.0, ((equity - self.peak) / self.peak) * 100.0) if self.peak > 0 else 0.0
            )
            self.points.append(dict(timestamp_ms=timestamp, equity=equity, drawdown_pct=drawdown))

    def preview(self):
        # Sampling previews is bounded; global extrema are preserved by the final sampler.
        stride = max(1, math.ceil(len(self.points) / (self.max_points - 1)))
        points = self.points[::stride]
        if self.points and (not points or points[-1] is not self.points[-1]):
            points.append(self.points[-1])
        return {"type": "preview", "equity_curve": points}

    def finish(self) -> dict[str, Any]:
        if descriptor(self.request, self.closes) != dict(self.saved):
            raise ReplayUnavailableError("fingerprint_mismatch")
        if self.fill_index != len(self.fills):
            raise ReplayUnavailableError("unsupported_replay_shape")
        points = sample(self.points, self.max_points)
        return {
            "type": "complete",
            "result": {
                "availability": "exact",
                "reason": None,
                "source_point_count": len(self.points),
                "returned_point_count": len(points),
                "sampled": len(points) != len(self.points),
                "equity_curve": points,
            },
        }


def unavailable(reason):
    return {
        "type": "complete",
        "result": {
            "availability": "unavailable",
            "reason": reason,
            "source_point_count": 0,
            "returned_point_count": 0,
            "sampled": False,
            "equity_curve": [],
        },
    }


async def stream_equity(
    run, fills, max_points, client_factory: Callable[[], Any] = AsyncDatabaseAccessorClient
) -> AsyncGenerator[dict[str, Any], None]:
    saved = run.replay_descriptor
    if saved is None:
        yield unavailable("replay_metadata_missing")
        return
    request = run.request_snapshot.to_request()
    if (
        len(request.symbols) != 1
        or request.data_granularity != DataGranularity.BAR
        or not valid_descriptor(saved)
    ):
        yield unavailable("unsupported_replay_shape")
        return
    try:
        replay = EquityReplayStream(request, saved, fills, max_points)
        next_preview_at = 0.0
        async with client_factory() as client:
            async with aclosing(
                client.stream_candles(
                    symbol=request.symbols[0],
                    exchange=request.exchange,
                    market_id=request.instrument.symbol_id if request.instrument else None,
                    timeframe="M1"
                    if request.execution.execution_mode == "orders"
                    else request.timeframe,
                    start_ms=request.start_ms,
                    end_ms=request.end_ms,
                )
            ) as batches:
                async for candles in batches:
                    replay.append(candles)
                    if time.monotonic() >= next_preview_at:
                        yield replay.preview()
                        next_preview_at = time.monotonic() + 0.1
                    await asyncio.sleep(0)
        yield await asyncio.to_thread(replay.finish)
    except ReplayUnavailableError as exc:
        yield unavailable(str(exc))
    except (ValueError, TypeError, KeyError, OverflowError):
        yield unavailable("unsupported_replay_shape")
    except Exception:
        yield {"type": "error", "message": "Equity replay could not be loaded. Please retry."}
