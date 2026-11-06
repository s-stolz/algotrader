"""Closed daily basket snapshots from raw storage and ingestion recovery state."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pandas as pd
from db_accessor_client import AsyncDatabaseAccessorClient

from app.services.anchored_indicator_service import _fetch_sources

if TYPE_CHECKING:
    from app.services.live_indicator_manager import LiveStreamSpec


async def _protection(client, market_ids: list[int], account_id: str):
    return await asyncio.gather(
        *[
            asyncio.gather(
                client.get_pending_recovery(market_id, account_id),
                client.get_live_write_guard(market_id, account_id),
            )
            for market_id in market_ids
        ]
    )


def _overlaps(protection: list[Any], start: int, end: int) -> bool:
    pending, guard = protection
    return bool(
        (pending and pending["next_ms"] < end and pending["target_ms"] >= start)
        or (guard and guard["boundary_ms"] < end)
    )


async def load_daily_snapshot(
    spec: LiveStreamSpec, assets: list[str], day: int, target: int, interval: int
) -> list[pd.DataFrame] | None:
    async with AsyncDatabaseAccessorClient() as client:
        markets = await asyncio.gather(
            *[client.get_market(asset, exchange=spec.exchange) for asset in assets]
        )
        market_ids = [int(market["symbol_id"]) for market in markets]
        before = await _protection(client, market_ids, spec.account_id)
        # Capture progress first: snapshots must include the writes proving that
        # their final minute is closed, not race ahead of that evidence.
        latest = await _fetch_sources(
            assets=assets,
            fields=["close"],
            timeframe="M1",
            exchange=spec.exchange,
            start_ms=None,
            end_ms=None,
            limit=1,
        )
        # Raw M1 avoids accepting a stale materialized aggregate after backfill.
        frames, predecessors = await asyncio.gather(
            _fetch_sources(
                assets=assets,
                fields=["close"],
                timeframe="M1",
                exchange=spec.exchange,
                start_ms=day,
                end_ms=target,
                limit=None,
            ),
            _fetch_sources(
                assets=assets,
                fields=["close"],
                timeframe="M1",
                exchange=spec.exchange,
                start_ms=None,
                end_ms=day,
                limit=1,
            ),
        )
        after = await _protection(client, market_ids, spec.account_id)
    snapshots = []
    for frame, prior, tail, initial, final in zip(
        frames, predecessors, latest, before, after, strict=True
    ):
        raw = pd.concat([prior, frame]).sort_index()
        start = int(raw.index[0]) if not raw.empty else day
        if _overlaps(initial, start, target) or _overlaps(final, start, target):
            return None
        bucket_times = raw.index.to_numpy(dtype="int64") // interval * interval
        buckets = raw.groupby(bucket_times).tail(1).copy()
        buckets.index = pd.Index(buckets.index.to_numpy(dtype="int64") // interval * interval)
        # A bucket can exist before its final M1 close is persisted. Later raw
        # progress also permits genuine market closures inside a predecessor.
        if interval > 60_000 and not buckets.empty:
            required = int(buckets.index[-1]) + interval - 60_000
            if tail.empty or int(tail.index[-1]) < required:
                return None
        snapshots.append(buckets)
    return snapshots
