"""Live daily basket alignment, chronological calculation and silent recovery."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from algotrader_logger import get_logger
from db_accessor_client import timeframe_to_minutes
from indicator_engine import ParamGrid
from indicator_engine.adapters.history import prepare_daily_inputs
from indicator_engine.core.history import UTC_DAY_MS
from indicator_engine.core.tensor import Tensor

from app import BATCH_ENGINE, ENGINE_REGISTRY
from app.services.anchored_indicator_service import _fetch_sources

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.typing import EncodableT, FieldT

    from app.services.live_indicator_manager import LiveStreamSpec

log = get_logger(__name__)


class LiveDailyBasket:
    """Keep one UTC day's source rows; never carry a price into another candle.

    History is rebuilt on candle transitions or older corrections. Revisions to
    the forming candle use the indicator's incremental state, avoiding a daily
    batch calculation on every tick. Redis cursors precede all history reads.
    """

    def __init__(self, spec: LiveStreamSpec):
        self.spec = spec
        self.indicator = ENGINE_REGISTRY.get(spec.engine_id)
        self.assets = list(self.indicator.spec.required_assets or [spec.symbol])
        self.interval = timeframe_to_minutes(spec.timeframe) * 60_000
        if self.interval > UTC_DAY_MS or UTC_DAY_MS % self.interval:
            raise ValueError("Daily anchored indicators require a timeframe dividing a UTC day")
        self.streams = {
            f"candles:{spec.account_id}:{asset}:{spec.timeframe}": asset for asset in self.assets
        }
        self.cursors: dict[str, str] = {}
        self.continuity: dict[str, str | None] = {}
        self.live: dict[str, dict[int, float]] = {asset: {} for asset in self.assets}
        self.predecessor_times: dict[str, int | None] = {}
        self.history: list[pd.DataFrame] = []
        self.target: int | None = None
        self.day: int | None = None
        self.state: dict | None = None
        self.needs_rebuild = True
        self.needs_history = True
        self.awaiting_snapshot = True
        self.next_recovery = 0.0
        self.recovery_from: int | None = None
        self.recovery_through: int | None = None
        self.published: dict[int, dict[str, float]] = {}
        self.has_baseline = False

    async def initialize(self, redis: Redis) -> None:
        for stream, asset in self.streams.items():
            tail: Any = await redis.xrevrange(stream, count=1)
            self.cursors[stream] = tail[0][0] if tail else "0-0"
            if tail:
                self.ingest(asset, tail[0][1])

    def require_recovery(self) -> None:
        # The last forming candle may have lost its final revision as well.
        starts = [max(rows) for rows in self.live.values() if rows]
        boundary = min(starts) if starts else self.target
        if boundary is not None:
            self.recovery_from = (
                boundary if self.recovery_from is None else min(self.recovery_from, boundary)
            )
        if self.target is not None:
            self.recovery_through = (
                self.target
                if self.recovery_through is None
                else max(self.recovery_through, self.target)
            )
        self.needs_history = True
        self.awaiting_snapshot = True
        self.needs_rebuild = True
        self.state = None

    def ingest(self, asset: str, fields: dict[str, Any]) -> None:
        try:
            timestamp = int(fields["t"])
            close = float(fields["c"])
        except (KeyError, ValueError, TypeError):
            self.require_recovery()
            return
        if timestamp % self.interval or not np.isfinite(close):
            self.require_recovery()
            return
        continuity = fields.get("continuity")
        if asset in self.continuity and continuity != self.continuity[asset]:
            self.require_recovery()
        self.continuity[asset] = continuity
        if self.day is not None and timestamp < self.day:
            self._remember_predecessor(asset, timestamp, close)
            return
        if self.target is None or timestamp > self.target:
            self.target = timestamp
            self.needs_rebuild = True
            self.state = None
        if self.target is not None and timestamp < self.target:
            if self.live[asset].get(timestamp) != close:
                self.needs_rebuild = True
                self.state = None
                if (
                    self.history
                    and not self.awaiting_snapshot
                    and (self.recovery_from is None or timestamp < self.recovery_from)
                ):
                    index = self.assets.index(asset)
                    self.history[index].loc[timestamp, "close"] = close
                    self.history[index] = self.history[index].sort_index()
        self.live[asset][timestamp] = close
        day = timestamp // UTC_DAY_MS * UTC_DAY_MS
        if self.day is None or day > self.day:
            self.day = day
            self.history = []
            self.published = {}
            self.needs_history = True
            self.awaiting_snapshot = True
            self.next_recovery = 0.0
            self.predecessor_times = {
                source: max((t for t in rows if t < day), default=None)
                for source, rows in self.live.items()
            }
            self.live = {
                source: {
                    t: value
                    for t, value in rows.items()
                    if t >= day or t == self.predecessor_times[source]
                }
                for source, rows in self.live.items()
            }

    def _remember_predecessor(self, asset: str, timestamp: int, close: float) -> None:
        previous = self.predecessor_times.get(asset)
        if previous is not None and timestamp < previous:
            return
        self.predecessor_times[asset] = timestamp
        if previous is not None:
            self.live[asset].pop(previous, None)
        self.live[asset][timestamp] = close
        self.needs_history = True
        self.awaiting_snapshot = True
        self.needs_rebuild = True
        self.state = None

    def _has_current_basket_and_predecessors(self, timestamp: int) -> bool:
        day = timestamp // UTC_DAY_MS * UTC_DAY_MS
        for asset, history in zip(self.assets, self.history, strict=True):
            if timestamp not in self.live[asset]:
                return False
            expected = self.predecessor_times.get(asset)
            prior = history.index[history.index < day]
            if expected is not None and (not len(prior) or int(prior[-1]) < expected):
                return False
        return True

    async def recover(self) -> None:
        if self.target is None or self.day is None:
            return
        self.next_recovery = time.monotonic() + 5.0
        frames, predecessors = await asyncio.gather(
            _fetch_sources(
                assets=self.assets,
                fields=["close"],
                timeframe=self.spec.timeframe,
                exchange=self.spec.exchange,
                start_ms=self.day,
                end_ms=self.target,
                limit=None,
            ),
            _fetch_sources(
                assets=self.assets,
                fields=["close"],
                timeframe=self.spec.timeframe,
                exchange=self.spec.exchange,
                start_ms=None,
                end_ms=self.day,
                limit=1,
            ),
        )
        self.history = [
            pd.concat([prior, frame]).sort_index()
            for prior, frame in zip(predecessors, frames, strict=True)
        ]
        self.needs_history = False
        self.awaiting_snapshot = False
        self.needs_rebuild = True
        self.state = None

    def _frames(self) -> list[pd.DataFrame]:
        frames = []
        for asset, history in zip(self.assets, self.history, strict=True):
            observed = self.live[asset]
            # A recovery snapshot owns closed candles. Keep observations that
            # storage hasn't received, except across a known delivery break.
            accepted = {
                t: close
                for t, close in observed.items()
                if t == self.target
                or (
                    t not in history.index
                    and (self.recovery_from is None or t < self.recovery_from)
                )
            }
            live = pd.DataFrame({"close": pd.Series(accepted, dtype=float)})
            frame = pd.concat([history, live])
            frames.append(frame.loc[~frame.index.duplicated(keep="last")].sort_index())
        return frames

    def _finish_recovery_if_closed(self, timestamp: int) -> None:
        if self.recovery_through is None or timestamp > self.recovery_through:
            self.recovery_from = None
            self.recovery_through = None
        self.needs_history = self.recovery_from is not None

    def calculate(self) -> list[tuple[int, dict[str, float], bool]]:
        if self.target is None or not self.history or self.awaiting_snapshot:
            return []
        if not self._has_current_basket_and_predecessors(self.target):
            self.needs_history = True
            return []
        outputs: dict[int, dict[str, float]] = {}
        if self.needs_rebuild:
            block = prepare_daily_inputs(
                self._frames(),
                self.assets,
                ["close"],
                np.array([self.target], dtype=np.int64),
                self.interval,
                1,
            )[0]
            tensor = BATCH_ENGINE.run(
                self.spec.engine_id, block.bars, ParamGrid(self.spec.parameters)
            ).tensor
            for index, valid in enumerate(block.available):
                values = tensor.data[index, 0, :, 0]
                if valid and np.isfinite(values).all():
                    outputs[int(block.bars.time[index])] = self._values(values)
            if not block.available[-1]:
                self.needs_history = True
                return self._changed(outputs)
            self.state = self.indicator.init_state(block.bars, self.spec.parameters)
            self.needs_rebuild = False
            self._finish_recovery_if_closed(self.target)
        if self.state is not None:
            row = np.array([[self.live[asset][self.target]] for asset in self.assets])
            self.state, values = self.indicator.update(
                self.state,
                new_row=row,
                asset_mask=np.ones(len(self.assets), dtype=bool),
                timestamp_ms=self.target,
            )
            if isinstance(values, Tensor):
                values = values.data
            if np.isfinite(values).all():
                outputs[self.target] = self._values(values[0])
        return self._changed(outputs)

    def _values(self, row: np.ndarray) -> dict[str, float]:
        return dict(zip(self.indicator.spec.outputs, map(float, row), strict=True))

    def _changed(
        self, outputs: dict[int, dict[str, float]]
    ) -> list[tuple[int, dict[str, float], bool]]:
        changed = []
        for timestamp, values in outputs.items():
            # Initial history is already supplied through the chart HTTP path.
            if not self.has_baseline and timestamp != self.target:
                self.published[timestamp] = values
                continue
            if self.published.get(timestamp) != values:
                replay = self.target is not None and timestamp < self.target
                changed.append((timestamp, values, replay))
        self.has_baseline = True
        return changed

    async def publish(self, redis: Redis, maxlen: int) -> None:
        for timestamp, values, replay in self.calculate():
            payload: dict[FieldT, EncodableT] = {
                "t": str(timestamp),
                "s": self.spec.stream_id,
                "i": str(self.spec.indicator_id),
                "d": json.dumps(values, separators=(",", ":")),
            }
            if replay:
                payload["replay"] = "1"
            await redis.xadd(
                self.spec.indicator_stream_key, payload, maxlen=maxlen, approximate=True
            )
            self.published[timestamp] = values

    async def run(self, redis: Redis, *, maxlen: int, count: int) -> None:
        while True:
            try:
                results: Any = await redis.xread(
                    {stream: cursor for stream, cursor in self.cursors.items()},
                    count=count,
                    block=1000,
                )
                for stream, messages in results:
                    for message_id, fields in messages:
                        self.ingest(self.streams[stream], fields)
                        self.cursors[stream] = message_id
                if self.needs_history and time.monotonic() >= self.next_recovery:
                    await self.recover()
                    # Drain changes that arrived during the snapshot before
                    # publishing; captured cursors make that handoff lossless.
                    continue
                await self.publish(redis, maxlen)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("Daily basket recovery pending for %s: %s", self.spec.stream_id, exc)
                self.require_recovery()
                await asyncio.sleep(1)
