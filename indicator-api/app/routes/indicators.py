from __future__ import annotations

from typing import Optional

from app import get_available_indicators
from app.schemas import IndicatorParameters
from app.services.historical_indicator_service import run_historical_indicator
from fastapi import APIRouter, Body, Query, Request

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("")
async def get_indicators() -> list[dict]:
    return get_available_indicators()


@router.post("/{indicator_id}")
async def run_indicator(
    request: Request,
    indicator_id: int,
    symbol: str = Query(..., description="The market symbol (e.g. EURUSD)"),
    exchange: Optional[str] = Query(None, description="Market exchange"),
    timeframe: str = Query(..., description="Timeframe code (e.g. M1, H1)"),
    start_ms: Optional[int] = Query(None, description="Start timestamp in epoch ms (UTC)"),
    end_ms: Optional[int] = Query(None, description="End timestamp in epoch ms (UTC)"),
    limit: Optional[int] = Query(None, description="Maximum number of records to return"),
    body: Optional[IndicatorParameters] = Body(None),
) -> dict:
    custom_parameters = getattr(body, "parameters", {})
    candle_cache = request.app.state.candle_cache

    return await run_historical_indicator(
        indicator_id=indicator_id,
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=limit,
        custom_parameters=custom_parameters,
        candle_cache=candle_cache,
    )
