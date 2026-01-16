from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Tuple

from app.domain.models import Trendbar
from app.domain.value_objects import (
    AccountId,
    Timeframe,
    TrendbarStreamOptions,
    TrendbarStreamStatus,
)
from app.infrastructure.stream_registry import TrendbarSubscription
from app.settings import Settings

logger = logging.getLogger(__name__)

TrendbarHandler = Callable[
    [Trendbar],
    Awaitable[None],
]
TrendbarPublisher = Callable[
    [AccountId, str, Timeframe, Trendbar],
    Awaitable[None],
]

# Type for subscribe/unsubscribe functions from CtraderClient
TrendbarSubscribeFn = Callable[
    [int, str, Timeframe, TrendbarHandler],
    Awaitable[TrendbarSubscription],
]
TrendbarUnsubscribeFn = Callable[[TrendbarSubscription], Awaitable[None]]


@dataclass(slots=True)
class TrendbarStreamEntry:
    subscription: TrendbarSubscription
    started_at: float
    only_completed_bars: bool
    last_bar_timestamp: int | None = None  # For deduplication
    pending_bar: Trendbar | None = None  # Buffer for the last update of current bar
    last_bar_at: float | None = None
    error: str | None = None


class TrendbarStreamRegistry:
    """Manages trendbar streaming lifecycle per account, symbol, and timeframe.

    Uses push-based live trendbar subscriptions from cTrader API instead of polling.
    Trendbars are delivered via ProtoOASpotEvent when subscribed to live trendbars
    and published directly to Redis as they arrive.
    """

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
        options: TrendbarStreamOptions | None = None,
    ) -> TrendbarStreamStatus:
        if options is None:
            options = TrendbarStreamOptions()

        async with self._lock:
            key = (int(account_id), symbol.upper(), timeframe.value)
            if key in self._streams:
                return self._to_status(self._streams[key])

            if len(self._streams) >= self._settings.broker_max_trendbar_streams:
                raise RuntimeError("Reached maximum number of concurrent trendbar streams")

            # Create entry first so the handler can access it
            entry = TrendbarStreamEntry(
                subscription=None,  # type: ignore[arg-type] # Will be set below
                started_at=time.time(),
                only_completed_bars=options.only_completed_bars,
            )
            self._streams[key] = entry

            async def on_trendbar(bar: Trendbar) -> None:
                # TODO: Refactor and cleanup
                """Handler called by CtraderClient when a live trendbar arrives."""
                stream_entry = self._streams.get(key)
                if stream_entry is None:
                    return

                if stream_entry.only_completed_bars:
                    # Check if this is a new bar (different timestamp)
                    if stream_entry.last_bar_timestamp is not None and bar.t > stream_entry.last_bar_timestamp:
                        # New bar started - publish the previous completed bar
                        if stream_entry.pending_bar is not None:
                            try:
                                await self._publish_candle(
                                    account_id,
                                    symbol.upper(),
                                    timeframe,
                                    stream_entry.pending_bar,
                                )
                                stream_entry.last_bar_at = time.time()
                            except Exception as exc:
                                logger.exception("Failed to publish trendbar to Redis")
                                stream_entry.error = str(exc)

                    # Always update the pending bar and timestamp
                    stream_entry.last_bar_timestamp = bar.t
                    stream_entry.pending_bar = bar
                else:
                    # Publish every update
                    try:
                        await self._publish_candle(
                            account_id,
                            symbol.upper(),
                            timeframe,
                            bar,
                        )
                        stream_entry.last_bar_at = time.time()
                    except Exception as exc:
                        logger.exception("Failed to publish trendbar to Redis")
                        stream_entry.error = str(exc)

            # Subscribe to live trendbars via cTrader
            subscription = await self._subscribe_fn(
                int(account_id),
                symbol.upper(),
                timeframe,
                on_trendbar,
            )
            entry.subscription = subscription

            return self._to_status(entry)

    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        async with self._lock:
            key = (int(account_id), symbol.upper(), timeframe.value)
            entry = self._streams.pop(key, None)
        if entry is None:
            return
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

    def _to_status(self, entry: TrendbarStreamEntry) -> TrendbarStreamStatus:
        uptime = time.time() - entry.started_at if entry.started_at else None
        return TrendbarStreamStatus(
            running=True,
            started_at=entry.started_at,
            last_bar_at=entry.last_bar_at,
            uptime_seconds=uptime,
            error=entry.error,
        )

    def active_stream_count(self) -> int:
        return len(self._streams)
