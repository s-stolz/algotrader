from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Awaitable, Callable, Dict, Tuple

from app.domain.models import Trendbar
from app.domain.value_objects import (
    AccountId,
    Timeframe,
    TrendbarStreamStatus,
)
from app.infrastructure.stream_registry import TrendbarSubscription
from app.settings import Settings

logger = logging.getLogger(__name__)

TrendbarHandler = Callable[[Trendbar], Awaitable[None]]
TrendbarPublisher = Callable[[AccountId, str, Timeframe, Trendbar], Awaitable[None]]

TrendbarSubscribeFn = Callable[
    [int, str, Timeframe, TrendbarHandler],
    Awaitable[TrendbarSubscription],
]
TrendbarUnsubscribeFn = Callable[[TrendbarSubscription], Awaitable[None]]


@dataclass(slots=True)
class TrendbarStreamEntry:
    subscription: TrendbarSubscription
    queue: asyncio.Queue[Trendbar]
    writer_task: asyncio.Task[None]
    account_id: AccountId
    symbol: str
    timeframe: Timeframe
    started_at: float
    last_bar_at: float | None = None
    error: str | None = None
    loss_revision: int = 0
    source_continuity: str | None = None
    continuity: str = field(default_factory=lambda: "v1:" + uuid.uuid4().hex)


class TrendbarStreamRegistry:
    """Manages trendbar streaming lifecycle per account, symbol, and timeframe."""

    def __init__(
        self,
        subscribe_fn: TrendbarSubscribeFn,
        unsubscribe_fn: TrendbarUnsubscribeFn,
        publisher: TrendbarPublisher,
        settings: Settings,
    ) -> None:
        self._subscribe_fn = subscribe_fn
        self._unsubscribe_fn = unsubscribe_fn
        self._publish_candle = publisher
        self._settings = settings
        self._streams: Dict[Tuple[int, str, str], TrendbarStreamEntry] = {}
        self._lock = asyncio.Lock()

    async def start_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus:
        normalized_symbol = symbol.upper()
        key = (int(account_id), normalized_symbol, timeframe.value)
        async with self._lock:
            existing = self._streams.get(key)
            if existing is not None:
                return self._to_status(existing)

            if len(self._streams) >= self._settings.broker_max_trendbar_streams:
                raise RuntimeError("Reached maximum number of concurrent trendbar streams")

            queue: asyncio.Queue[Trendbar] = asyncio.Queue(maxsize=self._settings.tick_queue_size)

            # Placeholder entry to make handler registration re-entrant safe.
            placeholder_subscription = TrendbarSubscription(
                account_id=int(account_id),
                symbol=normalized_symbol,
                symbol_id=0,
                timeframe=timeframe,
                token="pending",
            )
            placeholder_task = asyncio.create_task(asyncio.sleep(0))
            entry = TrendbarStreamEntry(
                subscription=placeholder_subscription,
                queue=queue,
                writer_task=placeholder_task,
                account_id=account_id,
                symbol=normalized_symbol,
                timeframe=timeframe,
                started_at=time.time(),
            )
            self._streams[key] = entry

            async def enqueue_bar(bar: Trendbar) -> None:
                stream_entry = self._streams.get(key)
                if stream_entry is None:
                    return
                if bar.continuity != stream_entry.source_continuity:
                    stream_entry.source_continuity = bar.continuity
                    stream_entry.continuity = "v1:" + uuid.uuid4().hex
                # Capture the source session before independent writer tasks run.
                bar = replace(bar, continuity=stream_entry.continuity)
                try:
                    stream_entry.queue.put_nowait(bar)
                except asyncio.QueueFull:
                    # Keep loss outside the lossy queue. The FIFO writer observes
                    # it before starting its next publication, including old bars.
                    stream_entry.loss_revision += 1
                    logger.warning(
                        "Candle queue overflow account=%s symbol=%s timeframe=%s revision=%s",
                        account_id,
                        normalized_symbol,
                        timeframe.value,
                        stream_entry.loss_revision,
                    )
                    _ = stream_entry.queue.get_nowait()
                    stream_entry.queue.put_nowait(bar)

            async def on_trendbar(bar: Trendbar) -> None:
                stream_entry = self._streams.get(key)
                if stream_entry is None:
                    return

                await enqueue_bar(bar)

            try:
                subscription = await self._subscribe_fn(
                    int(account_id),
                    normalized_symbol,
                    timeframe,
                    on_trendbar,
                )
            except BaseException:
                self._streams.pop(key, None)
                placeholder_task.cancel()
                await asyncio.gather(placeholder_task, return_exceptions=True)
                raise
            entry.subscription = subscription
            entry.writer_task = asyncio.create_task(self._writer(entry))
            entry.writer_task.add_done_callback(lambda task, e=entry: self._writer_done(e, task))
            return self._to_status(entry)

    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        key = (int(account_id), symbol.upper(), timeframe.value)
        async with self._lock:
            entry = self._streams.pop(key, None)
        if entry is None:
            return

        entry.writer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry.writer_task
        await self._unsubscribe_fn(entry.subscription)

    async def get_trendbar_stream_status(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus:
        async with self._lock:
            entry = self._streams.get((int(account_id), symbol.upper(), timeframe.value))
            if entry is None:
                return TrendbarStreamStatus(
                    running=False,
                    started_at=None,
                    last_bar_at=None,
                    uptime_seconds=None,
                    error=None,
                )
            return self._to_status(entry)

    async def shutdown(self) -> None:
        async with self._lock:
            keys = list(self._streams.keys())
        for account_id, symbol, timeframe_value in keys:
            try:
                await self.stop_trendbar_stream(
                    AccountId(account_id), symbol, Timeframe(timeframe_value)
                )
            except Exception:
                logger.exception(
                    "Failed to stop trendbar stream during shutdown: account=%s symbol=%s timeframe=%s",
                    account_id,
                    symbol,
                    timeframe_value,
                )

    async def _writer(self, entry: TrendbarStreamEntry) -> None:
        publication_source: tuple[str | None, int] | None = None
        publication_continuity = ""
        while True:
            bar = await entry.queue.get()
            backoff = 1
            while True:
                source = (bar.continuity, entry.loss_revision)
                if source != publication_source:
                    publication_source = source
                    publication_continuity = "v1:" + uuid.uuid4().hex
                try:
                    await self._publish_candle(
                        entry.account_id,
                        entry.symbol,
                        entry.timeframe,
                        replace(bar, continuity=publication_continuity),
                    )
                    entry.last_bar_at = time.time()
                    entry.error = None
                    break
                except Exception as exc:
                    # An uncertain XADD may have committed. Retrying with a new
                    # identity protects that interval for every consumer.
                    entry.loss_revision += 1
                    entry.error = str(exc)
                    logger.exception(
                        "Candle publication failed account=%s symbol=%s timeframe=%s "
                        "revision=%s retry=%s",
                        entry.account_id,
                        entry.symbol,
                        entry.timeframe.value,
                        entry.loss_revision,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(30, backoff * 2)

    @staticmethod
    def _writer_done(entry: TrendbarStreamEntry, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            entry.error = str(exc)

    def _to_status(self, entry: TrendbarStreamEntry) -> TrendbarStreamStatus:
        uptime = time.time() - entry.started_at if entry.started_at else None
        return TrendbarStreamStatus(
            running=not entry.writer_task.done(),
            started_at=entry.started_at,
            last_bar_at=entry.last_bar_at,
            uptime_seconds=uptime,
            error=entry.error,
        )

    def active_stream_count(self) -> int:
        return len(self._streams)
