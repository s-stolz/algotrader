import os
from typing import Optional

import pandas as pd
import uvicorn
from app import (
    BATCH_ENGINE,
    ENGINE_REGISTRY,
    get_available_indicators,
    get_engine_id,
    get_indicator_metadata,
)
from app.candles import get_candles
from app.schemas import IndicatorParameters
from app.utils import (
    adjust_fetch_bounds,
    format_indicator_response,
    prepare_parameters,
    tensor_to_dataframe_single,
    trim_indicator_output,
)
from db_accessor_client import normalize_timeframe_code, timeframe_to_minutes
from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from logger import LOG_LEVEL_UVICORN, logger

log = logger(__name__)


app = FastAPI(
    title="Indicator API",
    description="Indicator API for algotrader",
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
    symbol: str = Query(..., description="The market symbol (e.g. EURUSD)"),
    exchange: Optional[str] = Query(None, description="Market exchange"),
    timeframe: str = Query(..., description="Timeframe code (e.g. M1, H1)"),
    start_ms: Optional[int] = Query(None, description="Start timestamp in epoch ms (UTC)"),
    end_ms: Optional[int] = Query(None, description="End timestamp in epoch ms (UTC)"),
    limit: Optional[int] = Query(None, description="Maximum number of records to return"),
    body: Optional[IndicatorParameters] = Body(None),
) -> dict:
    timeframe_code = normalize_timeframe_code(timeframe)
    timeframe_minutes = timeframe_to_minutes(timeframe_code)
    metadata = get_indicator_metadata(indicator_id)

    custom_parameters = getattr(body, "parameters", {})
    parameters = prepare_parameters(
        metadata,
        custom_parameters,
        timeframe=timeframe_code,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=limit,
    )
    indicator_params = {k: v for k, v in parameters.items() if k in metadata["parameters"]}

    engine_id = get_engine_id(indicator_id)
    indicator = ENGINE_REGISTRY.get(engine_id)
    warmup = indicator.spec.warmup(indicator_params)

    fetch_start, fetch_limit, orig_start, orig_limit = adjust_fetch_bounds(
        start_ms=start_ms,
        limit=limit,
        timeframe=timeframe_minutes,
        warmup=warmup,
    )

    log.info(
        f"""Adjusted fetch bounds:
                start_ms={fetch_start},
                limit={fetch_limit} (
                    orig_start={orig_start},
                    orig_limit={orig_limit},
                    warmup={warmup}
                )
        """
    )

    if engine_id == "currency_strength":
        candles = await get_candles(
            symbol=metadata["inputs"],
            timeframe=timeframe_code,
            start_ms=fetch_start,
            end_ms=end_ms,
            limit=fetch_limit,
            exchange=exchange,
        )
        if not candles.empty and candles.columns.nlevels == 2:
            required_assets = metadata.get("inputs", [])
            try:
                close_df = candles.xs("close", level=0, axis=1)
            except KeyError:
                close_df = pd.DataFrame()
            if not close_df.empty:
                if required_assets:
                    available_assets = [a for a in required_assets if a in close_df.columns]
                    if available_assets:
                        close_df = close_df[available_assets]
                aligned_index = close_df.dropna(how="any").index
                candles = candles.loc[aligned_index]
    else:
        candles = await get_candles(
            symbol=symbol,
            timeframe=timeframe_code,
            start_ms=fetch_start,
            end_ms=end_ms,
            limit=fetch_limit,
            exchange=exchange,
        )

    log.debug(f"Fetched candles:\n{candles}")

    from indicator_engine.adapters import bars_from_dataframe
    from indicator_engine.core import ParamGrid

    bar_tensor = bars_from_dataframe(candles)
    param_grid = ParamGrid(indicator_params)
    indicator_result = BATCH_ENGINE.run(engine_id, bar_tensor, param_grid)
    indicator_raw = tensor_to_dataframe_single(indicator_result.tensor)

    dropna_how = "all" if engine_id == "currency_strength" else "any"
    indicator_data = trim_indicator_output(
        indicator_raw,
        original_start_ms=orig_start,
        original_limit=orig_limit,
        dropna_how=dropna_how,
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
