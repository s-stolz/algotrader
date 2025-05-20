from sqlalchemy import select, insert, delete, text
from app.models import markets
from typing import Optional
from datetime import datetime


async def get_market_by_id(session, symbol_id: int):
    stmt = select(markets).where(markets.c.symbol_id == symbol_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def insert_market(session, market_data: dict):
    stmt = insert(markets).values(**market_data).returning(markets.c.symbol_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def delete_market(session, symbol_id: int):
    stmt = delete(markets).where(markets.c.symbol_id == symbol_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def get_markets(session):
    stmt = select(markets)
    result = await session.execute(stmt)
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_symbol_id(session, symbol: str, exchange: str):
    query = text("""
        SELECT symbol_id FROM markets WHERE symbol = :symbol AND exchange LIKE :exchange
    """)
    result = await session.execute(query, {"symbol": symbol, "exchange": exchange})
    row = result.first()
    return row[0] if row else None


async def insert_candles(session, symbol: str, exchange: str, candles: list[dict]):
    symbol_id = await get_symbol_id(session, symbol, exchange)
    if not symbol_id:
        return None

    values = [
        {
            "symbol_id": symbol_id,
            **candle
        }
        for candle in candles
    ]

    stmt = insert(candles).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["symbol_id", "timestamp"])
    await session.execute(stmt)
    await session.commit()
    return True


async def get_candles(session, symbol_id: int, timeframe: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
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
            AND (timestamp <= :end_date OR :end_date IS NULL)
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
        ORDER BY timestamp
    """)

    start_date = datetime.fromisoformat(start_date) if start_date else None
    end_date = datetime.fromisoformat(end_date) if end_date else None
    params = {
        "symbol_id": symbol_id,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date
    }

    result = await session.execute(sql, params)
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]
