from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from logger import logger, LOG_LEVEL
from app.schemas import IndicatorParameters
from app.candles import get_candles
from app.utils import (
    prepare_parameters,
    format_indicator_response,
    estimate_warmup,
    adjust_fetch_bounds,
    trim_indicator_output,
)
from app.markets import load_symbols
import app.markets as markets
from app import get_available_indicators, get_indicator_by_id, get_indicator_metadata
from app.indicators.base import execute_indicator
import uvicorn
import os

from __init__ import __version__

logger.info(f"Starting Indicator API version {__version__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup/shutdown tasks.

    Preloads the global SYMBOL_MAPPING before serving requests so symbol ID
    lookups are fast and avoid per-request network calls. Failures are logged
    but don't abort startup.
    """
    try:
        await load_symbols()
        logger.info("[lifespan] Loaded %d symbols into cache", len(markets.SYMBOL_MAPPING))
    except Exception as exc:
        logger.warning("[lifespan] Failed to preload symbols: %s", exc)

    yield


app = FastAPI(
    title="Indicator API",
    description="Indicator API for algotrader",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Welcome to the Indicator API"}


@app.get("/indicators")
async def get_indicators() -> list[dict]:
    return get_available_indicators()


@app.post("/indicators/{indicator_id}")
async def run_indicator(
    indicator_id: int,
    symbol_id: int = Query(..., description="The ID of the market symbol"),
    timeframe: int = Query(..., description="The timeframe for the candles"),
    start_date: Optional[str] = Query(None, description="Start date for the data"),
    end_date: Optional[str] = Query(None, description="End date for the data"),
    limit: Optional[int] = Query(None, description="Maximum number of records to return"),
    body: Optional[IndicatorParameters] = Body(None),
) -> dict:
    metadata = get_indicator_metadata(indicator_id)
    query_params = {
        "symbol_id": symbol_id,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    }

    custom_parameters = getattr(body, 'parameters', {})
    parameters = prepare_parameters(metadata, custom_parameters, **query_params)

    # Determine warmup period to fetch extra history so user limit/start_date are honored.
    warmup = estimate_warmup(metadata, parameters)

    fetch_start, fetch_limit, orig_start, orig_limit = adjust_fetch_bounds(
        start_date=start_date,
        limit=limit,
        timeframe=timeframe,
        warmup=warmup,
    )

    logger.info(
        f"Adjusted fetch bounds: start_date={fetch_start}, limit={fetch_limit} (orig_start={orig_start}, orig_limit={orig_limit}, warmup={warmup})"
    )

    # Fetch with expanded bounds
    candles = await get_candles(
        symbol_id=symbol_id,
        timeframe=timeframe,
        start_date=fetch_start,
        end_date=end_date,
        limit=fetch_limit,
    )

    logger.debug(f"Fetched candles:\n{candles}")

    indicator_cls = get_indicator_by_id(indicator_id)
    indicator_raw = execute_indicator(
        indicator_cls,
        candles,
        **parameters,
    )

    indicator_data = trim_indicator_output(
        indicator_raw,
        original_start_date=orig_start,
        original_limit=orig_limit,
    )

    response = format_indicator_response(indicator_data, indicator_id, metadata)
    return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8010))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["/app"],
        log_level=LOG_LEVEL,
    )
