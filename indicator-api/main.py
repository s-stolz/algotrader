import os
from contextlib import asynccontextmanager
from typing import Optional

import app.markets as markets
import uvicorn
from app import get_available_indicators, get_indicator_by_id, get_indicator_metadata
from app.candles import get_candles
from app.indicators.base import execute_indicator
from app.markets import load_symbols
from app.schemas import IndicatorParameters
from app.utils import (
    adjust_fetch_bounds,
    estimate_warmup,
    format_indicator_response,
    prepare_parameters,
    trim_indicator_output,
)
from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from logger import LOG_LEVEL_UVICORN, logger

log = logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup/shutdown tasks.

    Preloads the global SYMBOL_MAPPING before serving requests so symbol ID
    lookups are fast and avoid per-request network calls. Failures are logged
    but don't abort startup.
    """
    try:
        await load_symbols()
        log.info("Loaded %d symbols into cache", len(markets.SYMBOL_MAPPING))
    except Exception as exc:
        log.warning("Failed to preload symbols: %s", exc)

    yield


app = FastAPI(
    title="Indicator API",
    description="Indicator API for algotrader",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


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
    indicators = get_available_indicators()
    log.debug(f"Available indicators: {indicators}")
    return indicators


@app.post("/indicators/{indicator_id}")
async def run_indicator(
    indicator_id: int,
    symbol_id: int = Query(..., description="The ID of the market symbol"),
    timeframe: int = Query(..., description="The timeframe for the candles"),
    start_ms: Optional[int] = Query(None, description="Start timestamp in epoch ms (UTC)"),
    end_ms: Optional[int] = Query(None, description="End timestamp in epoch ms (UTC)"),
    limit: Optional[int] = Query(None, description="Maximum number of records to return"),
    body: Optional[IndicatorParameters] = Body(None),
) -> dict:
    metadata = get_indicator_metadata(indicator_id)
    query_params = {
        "symbol_id": symbol_id,
        "timeframe": timeframe,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "limit": limit,
    }

    custom_parameters = getattr(body, "parameters", {})
    parameters = prepare_parameters(metadata, custom_parameters, **query_params)

    # Determine warmup period to fetch extra history so user limit/start_date are honored.
    warmup = estimate_warmup(metadata, parameters)

    fetch_start, fetch_limit, orig_start, orig_limit = adjust_fetch_bounds(
        start_ms=start_ms,
        limit=limit,
        timeframe=timeframe,
        warmup=warmup,
    )

    log.info(
        f"Adjusted fetch bounds: start_ms={fetch_start}, limit={fetch_limit} (orig_start={orig_start}, orig_limit={orig_limit}, warmup={warmup})"
    )

    # Fetch with expanded bounds
    candles = await get_candles(
        symbol_id=symbol_id,
        timeframe=timeframe,
        start_ms=fetch_start,
        end_ms=end_ms,
        limit=fetch_limit,
    )

    log.debug(f"Fetched candles:\n{candles}")

    indicator_cls = get_indicator_by_id(indicator_id)
    indicator_raw = execute_indicator(
        indicator_cls,
        candles,
        **parameters,
    )

    indicator_data = trim_indicator_output(
        indicator_raw,
        original_start_ms=orig_start,
        original_limit=orig_limit,
    )

    response = format_indicator_response(indicator_data, metadata)
    return response


if __name__ == "__main__":
    port = int(os.getenv("INDICATOR_API_PORT", 8010))
    host = os.getenv("INDICATOR_API_BIND_HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["/app"],
        log_level=LOG_LEVEL_UVICORN,
    )
