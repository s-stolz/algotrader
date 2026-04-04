from __future__ import annotations

import asyncio
from typing import Optional

from app import crud
from sqlalchemy.ext.asyncio import AsyncSession

_MARKETS: list[dict] = []
_MARKETS_BY_SYMBOL: dict[str, list[dict]] = {}
_MARKETS_BY_ID: dict[int, dict] = {}
_CACHE_LOCK = asyncio.Lock()


def _rebuild_cache(markets: list[dict]) -> None:
    global _MARKETS, _MARKETS_BY_SYMBOL, _MARKETS_BY_ID
    _MARKETS = list(markets)
    _MARKETS_BY_SYMBOL = {}
    _MARKETS_BY_ID = {}
    for market in markets:
        _MARKETS_BY_ID[market["symbol_id"]] = market
        _MARKETS_BY_SYMBOL.setdefault(market["symbol"], []).append(market)

    for entries in _MARKETS_BY_SYMBOL.values():
        entries.sort(key=lambda m: m["symbol_id"])


async def refresh_market_cache(session: AsyncSession) -> list[dict]:
    markets = await crud.get_markets(session)
    _rebuild_cache(markets)
    return markets


async def ensure_market_cache(session: AsyncSession) -> list[dict]:
    if _MARKETS:
        return _MARKETS
    async with _CACHE_LOCK:
        if not _MARKETS:
            return await refresh_market_cache(session)
    return _MARKETS


async def get_cached_markets(
    session: AsyncSession,
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
) -> list[dict]:
    markets = await ensure_market_cache(session)
    if symbol is not None:
        markets = [m for m in markets if m["symbol"] == symbol]
    if exchange is not None:
        markets = [m for m in markets if m["exchange"] == exchange]
    return markets


def resolve_symbol_id(
    symbol: str,
    exchange: Optional[str] = None,
    reject_ambiguous: bool = False,
) -> int | None:
    markets = _MARKETS_BY_SYMBOL.get(symbol, [])
    if exchange:
        for market in markets:
            if market["exchange"] == exchange:
                return market["symbol_id"]
        return None
    if reject_ambiguous and len(markets) > 1:
        raise ValueError(f"Ambiguous symbol '{symbol}': provide exchange")
    if markets:
        return markets[0]["symbol_id"]
    return None


def resolve_symbol(symbol_id: int) -> dict | None:
    return _MARKETS_BY_ID.get(symbol_id)
