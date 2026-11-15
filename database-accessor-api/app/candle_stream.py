"""Bounded, cursor-backed historical Candle delivery."""

import asyncio
import json
from contextlib import aclosing

from anyio import CancelScope
from app.crud import CAGG_VIEW_BY_MINUTES
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

BATCH_SIZE = 1024


def candle_query(timeframe: int, *, aggregate: bool = False) -> str:
    fields = "open, high, low, close, volume"
    column = "timestamp_utc"
    source = "candles"
    if not aggregate and timeframe in CAGG_VIEW_BY_MINUTES:
        source = CAGG_VIEW_BY_MINUTES[timeframe]
        column = "bucket_ts"
    predicate = (
        f"symbol_id = :symbol_id AND {column} >= to_timestamp(:start_ms / 1000.0) "
        f"AND {column} < to_timestamp(:end_ms / 1000.0)"
    )
    if aggregate:
        return f"""
            SELECT CAST(EXTRACT(EPOCH FROM bucket_ts) * 1000 AS BIGINT) AS timestamp_ms,
                   first(open, timestamp_utc) AS open, max(high) AS high, min(low) AS low,
                   last(close, timestamp_utc) AS close, sum(volume) AS volume
            FROM (SELECT *, time_bucket(make_interval(mins => :timeframe), timestamp_utc)
                  AS bucket_ts FROM candles WHERE {predicate}) source
            GROUP BY bucket_ts ORDER BY bucket_ts
        """
    return (
        f"SELECT CAST(EXTRACT(EPOCH FROM {column}) * 1000 AS BIGINT) AS timestamp_ms, "
        f"{fields} FROM {source} WHERE {predicate} ORDER BY {column}"
    )


async def candle_batches(session, symbol_id: int, timeframe: int, start_ms: int, end_ms: int):
    params = dict(symbol_id=symbol_id, timeframe=timeframe, start_ms=start_ms, end_ms=end_ms)
    aggregate = timeframe != 1 and timeframe not in CAGG_VIEW_BY_MINUTES
    try:
        result = await session.stream(text(candle_query(timeframe, aggregate=aggregate)), params)
    except SQLAlchemyError:
        if timeframe not in CAGG_VIEW_BY_MINUTES:
            raise
        await session.rollback()
        result = await session.stream(text(candle_query(timeframe, aggregate=True)), params)
    found = False
    try:
        async for rows in result.partitions(BATCH_SIZE):
            found = True
            yield [dict(row._mapping) for row in rows]
            await asyncio.sleep(0)
    finally:
        with CancelScope(shield=True):
            await result.close()
    if not found and timeframe in CAGG_VIEW_BY_MINUTES:
        result = await session.stream(text(candle_query(timeframe, aggregate=True)), params)
        try:
            async for rows in result.partitions(BATCH_SIZE):
                yield [dict(row._mapping) for row in rows]
                await asyncio.sleep(0)
        finally:
            with CancelScope(shield=True):
                await result.close()


async def candle_messages(session_factory, symbol_id, timeframe, start_ms, end_ms):
    async with session_factory() as session:
        async with aclosing(
            candle_batches(session, symbol_id, timeframe, start_ms, end_ms)
        ) as batches:
            async for candles in batches:
                yield json.dumps({"type": "candles", "candles": jsonable_encoder(candles)}) + "\n"
    yield '{"type":"complete"}\n'
