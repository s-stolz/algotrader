from datetime import datetime, timezone
from typing import Optional

from app.models import candles, markets
from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert


def _epoch_ms_to_utc_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


async def get_market_by_id(session, symbol_id: int):
    """
    Get market by symbol_id

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id

    :return: Market data as a dictionary
    :rtype: dict or None
    """
    stmt = select(markets).where(markets.c.symbol_id == symbol_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def insert_market(session, market_data: dict):
    """
    Insert a new market into the database

    :param session: SQLAlchemy session
    :param market_data: Market data as a dictionary

    :return: The symbol_id of the newly inserted market
    :rtype: int
    """
    stmt = insert(markets).values(**market_data).returning(markets.c.symbol_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def delete_market(session, symbol_id: int):
    """
    Delete a market and all candles from that market from the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id

    :return: Number of rows in candles deleted
    :rtype: int
    """
    stmt = delete(candles).where(candles.c.symbol_id == symbol_id)
    candles_result = await session.execute(stmt)

    stmt = delete(markets).where(markets.c.symbol_id == symbol_id)
    market_result = await session.execute(stmt)

    await session.commit()

    return {
        "market_deleted": bool(market_result.rowcount),
        "deleted_candles": candles_result.rowcount,
    }


async def get_markets(session, symbol: Optional[str] = None, exchange: Optional[str] = None):
    """
    Get all markets from the database

    :param session: SQLAlchemy session

    :return: List of markets as dictionaries
    """
    stmt = select(markets)
    if symbol:
        stmt = stmt.where(markets.c.symbol == symbol)
    if exchange:
        stmt = stmt.where(markets.c.exchange == exchange)

    result = await session.execute(stmt)
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_symbol_id(session, symbol: str, exchange: str):
    """
    Get symbol_id from the markets table based on symbol and exchange

    :param session: SQLAlchemy session
    :param symbol: Market symbol
    :param exchange: Market exchange

    :return: symbol_id if found, None otherwise
    :rtype: int or None

    :raises ValueError: If symbol or exchange is not provided
    :raises TypeError: If symbol or exchange is not a string
    """

    if not symbol or not exchange:
        raise ValueError("Symbol and exchange must be provided")
    if not isinstance(symbol, str) or not isinstance(exchange, str):
        raise TypeError("Symbol and exchange must be strings")

    query = text("""
        SELECT symbol_id FROM markets WHERE symbol = :symbol AND exchange LIKE :exchange
    """)
    result = await session.execute(query, {"symbol": symbol, "exchange": exchange})
    row = result.first()
    return row[0] if row else None


async def insert_candles(session, symbol_id: int, candles_data: list[dict]):
    """
    Insert candles into the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id
    :param candles_data: List of candles to insert

    :return: Number of candles added
    :rtype: int
    """
    values = [
        {
            "symbol_id": symbol_id,
            "timestamp_utc": _epoch_ms_to_utc_datetime(candle["timestamp_ms"]),
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
        }
        for candle in candles_data
    ]

    stmt = pg_insert(candles).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["symbol_id", "timestamp_utc"])
    result = await session.execute(stmt)
    await session.commit()

    added = result.rowcount if result.rowcount is not None else len(values)
    return added


async def get_candles(
    session, symbol_id: int, timeframe: int,
    start_ms: Optional[int] = None, end_ms: Optional[int] = None,
    limit: Optional[int] = None
):
    """
    Get candles from the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id
    :param timeframe: Timeframe in minutes
    :param start_ms: Start timestamp in epoch ms (optional)
    :param end_ms: End timestamp in epoch ms (optional)
    :param limit: Maximum number of candles to return (optional)

    :return: List of candles as dictionaries
    :rtype: list[dict]
    """

    sql = text("""
        WITH BucketedCandles AS (
            SELECT
                time_bucket(make_interval(mins => :timeframe), timestamp_utc) AS bucket_ts,
                open,
                high,
                low,
                close,
                volume,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, time_bucket(make_interval(mins => :timeframe), timestamp_utc)
                    ORDER BY timestamp_utc ASC
                ) AS rn_asc,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, time_bucket(make_interval(mins => :timeframe), timestamp_utc)
                    ORDER BY timestamp_utc DESC
                ) AS rn_desc
            FROM candles
            WHERE symbol_id = :symbol_id
            AND (
                timestamp_utc >= to_timestamp(:start_ms / 1000.0)
                OR :start_ms IS NULL
            )
            AND (
                timestamp_utc < to_timestamp(:end_ms / 1000.0)
                OR :end_ms IS NULL
            )
        )
        SELECT
            CAST(EXTRACT(EPOCH FROM bucket_ts) * 1000 AS BIGINT) AS timestamp_ms,
            MAX(open) FILTER (WHERE rn_asc = 1) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            MAX(close) FILTER (WHERE rn_desc = 1) AS close,
            SUM(volume) AS volume
        FROM BucketedCandles
        GROUP BY bucket_ts
        ORDER BY bucket_ts {order_direction}
        {limit_clause}
    """.format(
        order_direction="DESC" if limit else "ASC",
        limit_clause="LIMIT :limit" if limit else ""
    ))

    params = {
        "symbol_id": symbol_id,
        "timeframe": timeframe,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }

    if limit is not None:
        params["limit"] = limit

    result = await session.execute(sql, params)
    rows = result.fetchall()

    if limit is not None:
        rows = list(reversed(rows))

    return [dict(row._mapping) for row in rows]


async def delete_candles(session, symbol_id: int):
    """
    Delete all candles for a given symbol_id

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id

    :return: Number of candles deleted
    :rtype: int
    """
    stmt = delete(candles).where(candles.c.symbol_id == symbol_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
