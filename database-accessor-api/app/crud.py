from sqlalchemy import select, insert, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import markets, candles
from typing import Optional
from datetime import datetime


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
            **candle
        }
        for candle in candles_data
    ]

    stmt = pg_insert(candles).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["symbol_id", "timestamp"])
    result = await session.execute(stmt)
    await session.commit()

    added = result.rowcount if result.rowcount is not None else len(values)
    return added


async def get_candles(
    session, symbol_id: int, timeframe: int,
    _start_date: Optional[str] = None, _end_date: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Get candles from the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id
    :param timeframe: Timeframe in minutes
    :param start_date: Start date in ISO format (optional)
    :param end_date: End date in ISO format (optional)
    :param limit: Maximum number of candles to return (optional)

    :return: List of candles as dictionaries
    :rtype: list[dict]
    """

    sql = text("""
        WITH RoundedCandles AS (
            SELECT
                date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                    ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                    ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % :timeframe)
                ) AS rounded_timestamp,
                open,
                high,
                low,
                close,
                volume,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % :timeframe)
                    )
                    ORDER BY timestamp ASC
                ) AS rn_asc,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % :timeframe)
                    )
                    ORDER BY timestamp DESC
                ) AS rn_desc
            FROM candles
            WHERE symbol_id = :symbol_id
            AND (timestamp >= :start_date OR :start_date IS NULL)
            AND (timestamp < :end_date OR :end_date IS NULL)
        )
        SELECT
            rounded_timestamp AS timestamp,
            MAX(open) FILTER (WHERE rn_asc = 1) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            MAX(close) FILTER (WHERE rn_desc = 1) AS close,
            SUM(volume) AS volume
        FROM RoundedCandles
        GROUP BY timestamp
        ORDER BY timestamp {order_direction}
        {limit_clause}
    """.format(
        order_direction="DESC" if limit else "ASC",
        limit_clause="LIMIT :limit" if limit else ""
    ))

    start_date = datetime.fromisoformat(_start_date) if _start_date else None
    end_date = datetime.fromisoformat(_end_date) if _end_date else None
    params = {
        "symbol_id": symbol_id,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
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
