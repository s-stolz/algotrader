"""Forward candle pages, including history outside aggregate retention."""

from app.candle_stream import candle_query
from sqlalchemy import text


async def forward_candles(
    session, symbol_id: int, timeframe: int, start_ms: int, end_ms: int, limit: int
):
    # Raw bucketing prevents a retained aggregate suffix from skipping older bars.
    query = candle_query(timeframe, aggregate=timeframe != 1) + " LIMIT :limit"
    result = await session.execute(
        text(query),
        dict(
            symbol_id=symbol_id, timeframe=timeframe, start_ms=start_ms, end_ms=end_ms, limit=limit
        ),
    )
    return [dict(row._mapping) for row in result.fetchall()]
