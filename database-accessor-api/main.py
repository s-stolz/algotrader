from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.database import get_db
from app.schemas import CandleBatchIn, MarketIn
from app import crud
from . import __version__

app = FastAPI(
    title="Database Accessor API",
    description="Database accessor API for algotrader",
    version=__version__
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


@app.get("/markets/{symbol_id}")
async def get_market(symbol_id: int, db: AsyncSession = Depends(get_db)):
    market = await crud.get_market_by_id(db, symbol_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@app.get("/markets")
async def read_markets(db: AsyncSession = Depends(get_db)):
    return await crud.get_markets(db)


@app.post("/markets")
async def create_market(market: MarketIn, db: AsyncSession = Depends(get_db)):
    symbol_id = await crud.insert_market(db, market.model_dump())
    return {"symbol_id": symbol_id, "status": "created"}


@app.delete("/markets/{symbol_id}")
async def delete_market(symbol_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_market(db, symbol_id)
    if deleted:
        return {"status": "deleted", "deleted_count": deleted}
    return {"status": "not found"}


@app.get("/candles/{symbol_id}")
async def read_aggregated_candles(
    symbol_id: int,
    timeframe: int = Query(..., description="Timeframe in minutes"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    return await crud.get_candles(db, symbol_id, timeframe, start_date, end_date, limit)


@app.post("/candles")
async def insert_candle_batch(data: CandleBatchIn, db: AsyncSession = Depends(get_db)):
    candles = [candle.model_dump() for candle in data.candles]
    added_candles = await crud.insert_candles(db, data.symbol, data.exchange, candles)

    if added_candles is None:
        return {"status": "error", "detail": "Symbol not found or exchange mismatch"}

    return {"status": "ok", "added_candles": added_candles}
