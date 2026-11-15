"""Fence delayed Candle writes against a deleted or renamed Market."""

from app.models import markets
from sqlalchemy import select


async def lock_market(session, market_id: int, symbol: str, exchange: str | None):
    result = await session.execute(
        select(markets).where(markets.c.symbol_id == market_id).with_for_update()
    )
    market = result.mappings().first()
    if market is None:
        return None
    if market["symbol"] != symbol.strip().upper() or (
        exchange is not None and market["exchange"] != exchange.strip().upper()
    ):
        raise ValueError("Candle source no longer matches the expected Market")
    return market["symbol_id"]
