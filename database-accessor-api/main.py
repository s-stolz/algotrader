from typing import Optional

from app import crud, market_cache
from app.database import get_db
from app.schemas import CandleBatchIn, MarketIn
from app.timeframes import TimeframeCode, timeframe_to_minutes
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI(
    title="Database Accessor API",
    description="Database accessor API for algotrader",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Welcome to the Database Accessor API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/markets")
async def read_markets(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by market symbol"),
    exchange: Optional[str] = Query(None, description="Filter by market exchange"),
):
    return await market_cache.get_cached_markets(db, symbol=symbol, exchange=exchange)


@app.get("/markets/{symbol}")
async def get_market(
    symbol: str,
    exchange: Optional[str] = Query(None, description="Market exchange"),
    db: AsyncSession = Depends(get_db),
):
    markets = await market_cache.get_cached_markets(db, symbol=symbol, exchange=exchange)
    if not markets:
        raise HTTPException(status_code=404, detail="Market not found")
    markets = sorted(markets, key=lambda m: m["symbol_id"])
    return markets[0]


@app.post("/markets")
async def create_market(market: MarketIn, db: AsyncSession = Depends(get_db)):
    symbol_id = await crud.insert_market(db, market.model_dump())
    await market_cache.refresh_market_cache(db)
    return {"symbol_id": symbol_id, "status": "created"}


@app.delete("/markets/{symbol}")
async def delete_market(
    symbol: str,
    exchange: Optional[str] = Query(None, description="Market exchange"),
    db: AsyncSession = Depends(get_db),
):
    await market_cache.ensure_market_cache(db)
    try:
        symbol_id = market_cache.resolve_symbol_id(
            symbol,
            exchange,
            reject_ambiguous=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        try:
            symbol_id = market_cache.resolve_symbol_id(
                symbol,
                exchange,
                reject_ambiguous=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    deleted = await crud.delete_market(db, symbol_id)
    await market_cache.refresh_market_cache(db)
    if deleted:
        return {"status": "deleted", "deleted_count": deleted}
    return {"status": "not found"}


@app.get("/candles/{symbol}")
async def read_aggregated_candles_by_symbol(
    symbol: str,
    exchange: Optional[str] = Query(None, description="Market exchange"),
    timeframe: TimeframeCode = Query(..., description="Timeframe code (e.g. M1, H1)"),
    start_ms: Optional[int] = Query(None, description="Start timestamp in epoch ms (UTC)"),
    end_ms: Optional[int] = Query(None, description="End timestamp in epoch ms (UTC)"),
    limit: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    await market_cache.ensure_market_cache(db)
    symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    return await crud.get_candles(
        db,
        symbol_id,
        timeframe_to_minutes(timeframe),
        start_ms,
        end_ms,
        limit,
    )


@app.post("/candles")
async def insert_candle_batch(data: CandleBatchIn, db: AsyncSession = Depends(get_db)):
    await market_cache.ensure_market_cache(db)
    symbol_id = market_cache.resolve_symbol_id(data.symbol, data.exchange)
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        symbol_id = market_cache.resolve_symbol_id(data.symbol, data.exchange)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    candles = [candle.model_dump() for candle in data.candles]
    batch_size = 4000
    total_added = 0

    for i in range(0, len(candles), batch_size):
        batch = candles[i:i + batch_size]
        added_candles = await crud.insert_candles(db, symbol_id, batch)

        total_added += added_candles

    return {"status": "ok", "added_candles": total_added, "total_candles": len(candles)}


@app.delete("/candles/{symbol}")
async def delete_candles(
    symbol: str,
    exchange: Optional[str] = Query(None, description="Market exchange"),
    db: AsyncSession = Depends(get_db),
):
    await market_cache.ensure_market_cache(db)
    try:
        symbol_id = market_cache.resolve_symbol_id(
            symbol,
            exchange,
            reject_ambiguous=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        try:
            symbol_id = market_cache.resolve_symbol_id(
                symbol,
                exchange,
                reject_ambiguous=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    deleted_count = await crud.delete_candles(db, symbol_id)

    return {"status": "deleted", "deleted_count": deleted_count}
