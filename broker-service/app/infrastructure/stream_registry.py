from __future__ import annotations

import asyncio
import contextlib
import time
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Tuple

from app.application.interfaces import StreamRegistryPort
from app.domain.models import Tick
from app.domain.value_objects import (
    AccountId,
    TickStreamOptions,
    TickStreamStatus
)
from app.settings import Settings
from app.domain.value_objects import Timeframe

TickHandler = Callable[[Tick], Awaitable[None]]
TickPublisher = Callable[[Tick, AccountId, str], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TickSubscription:
    account_id: int
    symbol: str
    symbol_id: int
    token: str


@dataclass(slots=True)
class TrendbarSubscription:
    account_id: int
    symbol: str
    symbol_id: int
    timeframe: "Timeframe"
    token: str


@dataclass(slots=True)
class StreamEntry:
    subscription: TickSubscription
    queue: asyncio.Queue[Tick]
    writer_task: asyncio.Task[None]
    started_at: float
    last_tick_at: float | None = None
    error: str | None = None


class StreamRegistry(StreamRegistryPort):
    def __init__(
        self,
        subscribe_fn: Callable[
            [int, str, TickHandler],
            Awaitable[TickSubscription]
        ],
        unsubscribe_fn: Callable[
            [TickSubscription],
            Awaitable[None]
        ],
        publisher: TickPublisher,
        settings: Settings,
    ) -> None:
        self._subscribe_fn = subscribe_fn
        self._unsubscribe_fn = unsubscribe_fn
        self._publish_tick = publisher
        self._settings = settings
        self._streams: Dict[Tuple[int, str], StreamEntry] = {}
        self._lock = asyncio.Lock()

    async def start_tick_stream(
        self,
        account_id: AccountId,
        symbol: str,
        options: TickStreamOptions,
    ) -> TickStreamStatus:
        async with self._lock:
            key = (int(account_id), symbol)
            if key in self._streams:
                return self._to_status(self._streams[key])

            if len(self._streams) >= self._settings.broker_max_symbol_streams:
                raise RuntimeError("Reached maximum number of concurrent tick streams")

            queue_size = options.queue_size or self._settings.tick_queue_size
            queue: asyncio.Queue[Tick] = asyncio.Queue(maxsize=queue_size)

            async def push_tick(tick: Tick) -> None:
                entry = self._streams.get(key)
                if entry is None:
                    return
                try:
                    queue.put_nowait(tick)
                except asyncio.QueueFull:
                    _ = queue.get_nowait()
                    queue.put_nowait(tick)
                entry.last_tick_at = tick.t / 1000

            subscription = await self._subscribe_fn(
                int(account_id),
                symbol,
                push_tick
            )
            writer_task = asyncio.create_task(
                self._writer(queue, options, subscription)
            )

            entry = StreamEntry(
                subscription=subscription,
                queue=queue,
                writer_task=writer_task,
                started_at=time.time(),
            )
            self._streams[key] = entry
            writer_task.add_done_callback(
                lambda t, e=entry: self._writer_done(e, t)
            )
            return self._to_status(entry)

    async def shutdown(self) -> None:
        async with self._lock:
            keys = list(self._streams.keys())
        for account_id, symbol in keys:
            try:
                await self.stop_tick_stream(AccountId(account_id), symbol)
            except Exception:
                logger.exception(
                    "Failed to stop tick stream during shutdown: account=%s symbol=%s",
                    account_id,
                    symbol,
                )

    async def stop_tick_stream(self, account_id: AccountId, symbol: str) -> None:
        async with self._lock:
            key = (int(account_id), symbol)
            entry = self._streams.pop(key, None)
        if entry is None:
            return
        entry.writer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry.writer_task
        await self._unsubscribe_fn(entry.subscription)

    async def get_tick_stream_status(
        self,
        account_id: AccountId,
        symbol: str
    ) -> TickStreamStatus:
        async with self._lock:
            entry = self._streams.get((int(account_id), symbol))
            if entry is None:
                return TickStreamStatus(
                    running=False,
                    started_at=None,
                    last_tick_at=None,
                    uptime_seconds=None,
                    error=None,
                )
            return self._to_status(entry)

    async def _writer(
        self,
        queue: asyncio.Queue[Tick],
        options: TickStreamOptions,
        subscription: TickSubscription,
    ) -> None:
        while True:
            tick = await queue.get()
            try:
                await self._publish_tick(
                    tick,
                    AccountId(subscription.account_id),
                    subscription.symbol,
                )
            finally:
                queue.task_done()

    def _writer_done(
        self,
        entry: StreamEntry,
        task: asyncio.Task[None]
    ) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            entry.error = str(exc)

    def _to_status(self, entry: StreamEntry) -> TickStreamStatus:
        uptime = time.time() - entry.started_at if entry.started_at else None
        return TickStreamStatus(
            running=not entry.writer_task.done(),
            started_at=entry.started_at,
            last_tick_at=entry.last_tick_at,
            uptime_seconds=uptime,
            error=entry.error,
        )

    def active_stream_count(self) -> int:
        return len(self._streams)
