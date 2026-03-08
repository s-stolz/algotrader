from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_account_id, get_market_data_service
from app.api.serialization import (
    serialize_symbol,
    serialize_symbol_light,
    serialize_tick_stream_status,
    serialize_trendbar_stream_status,
)
from app.api.validation import parse_tick_stream_body, read_json_body
from app.application.services import MarketDataService
from app.domain.value_objects import (
    AccountId,
    TickStreamOptions,
    Timeframe,
)

router = APIRouter(prefix="/symbols", tags=["market-data"])
logger = logging.getLogger(__name__)


def _options_from_inputs(
    queue_size: int | None,
    max_stream_length: int | None,
    body_values: tuple[int | None, int | None] | None,
) -> TickStreamOptions:
    if body_values is not None:
        body_queue, body_max = body_values
        if body_queue is not None:
            queue_size = body_queue
        if body_max is not None:
            max_stream_length = body_max

    return TickStreamOptions(
        queue_size=queue_size,
        max_stream_length=max_stream_length,
    )


@router.get("/")
async def list_symbols(
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> list[dict[str, Any]]:
    symbols = await service.list_symbols(account_id)
    return [serialize_symbol_light(symbol) for symbol in symbols]


@router.get("/{symbol}")
async def get_symbol(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    symbol_info = await service.get_symbol(account_id, normalized_symbol)
    if symbol_info is None:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return serialize_symbol(symbol_info)


@router.get("/{symbol}/tick-stream/start")
async def start_tick_stream(
    symbol: str,
    request: Request,
    queueSize: int | None = Query(default=None, ge=1),
    maxStreamLength: int | None = Query(default=None, ge=100),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    body_values: tuple[int | None, int | None] | None = None
    if request.headers.get("content-length") not in {None, "0"}:
        body_values = parse_tick_stream_body(await read_json_body(request))

    status = await service.start_tick_stream(
        account_id,
        normalized_symbol,
        _options_from_inputs(queueSize, maxStreamLength, body_values),
    )
    return serialize_tick_stream_status(status)


@router.get("/{symbol}/tick-stream/stop")
async def stop_tick_stream(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, str]:
    normalized_symbol = symbol.upper()
    await service.stop_tick_stream(account_id, normalized_symbol)
    return {"status": "stopped", "symbol": normalized_symbol}


@router.get("/{symbol}/tick-stream/status")
async def tick_stream_status(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    status = await service.tick_stream_status(account_id, normalized_symbol)
    return serialize_tick_stream_status(status)


@router.get("/{symbol}/trendbars")
async def get_trendbars(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    from_ts: int | None = Query(
        default=None,
        alias="fromTs",
        description="From timestamp (epoch millis). Required if limit not specified.",
    ),
    to_ts: int | None = Query(
        default=None,
        alias="toTs",
        description="To timestamp (epoch millis). Defaults to now if not specified.",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Max number of bars to return. If specified, fetches most recent bars up to limit.",
    ),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> list[dict[str, Any]]:
    tf = timeframe
    normalized_symbol = symbol.upper()

    if from_ts is None and limit is None:
        raise HTTPException(status_code=400, detail="Either 'fromTs' or 'limit' must be specified")

    now_ms = int(time.time() * 1000)

    if to_ts is None:
        to_ts = now_ms

    if from_ts is None and limit:
        timeframe_minutes = {
            "M1": 1,
            "M2": 2,
            "M3": 3,
            "M4": 4,
            "M5": 5,
            "M10": 10,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "H12": 720,
            "D1": 1440,
            "W1": 10080,
            "MN1": 43200,
        }.get(tf.value, 1)
        from_ts = to_ts - (limit * timeframe_minutes * 60 * 1000 * 3)

    bars = await service.get_trendbars(
        account_id,
        normalized_symbol,
        tf,
        from_ts,
        to_ts,
        limit,
    )

    response: list[dict[str, Any]] = []
    for bar in bars:
        response.append(
            {
                "o": float(bar.o) if isinstance(bar.o, Decimal) else bar.o,
                "h": float(bar.h) if isinstance(bar.h, Decimal) else bar.h,
                "l": float(bar.l) if isinstance(bar.l, Decimal) else bar.l,
                "c": float(bar.c) if isinstance(bar.c, Decimal) else bar.c,
                "v": bar.v,
                "t": bar.t,
            }
        )
    return response


@router.get("/{symbol}/trendbars/stream")
async def stream_trendbars(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    from_ts: int = Query(default=0, alias="fromTs", description="From timestamp (epoch millis)"),
    to_ts: int | None = Query(
        default=2147483646000, alias="toTs", description="To timestamp (epoch millis)"
    ),
    limit: int | None = Query(default=None, ge=1),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> StreamingResponse:
    tf = timeframe
    _from_ts = from_ts
    _to_ts = to_ts
    _limit = limit
    _account_id = account_id
    _symbol = symbol.upper()
    _tf = tf

    async def generate_ndjson() -> AsyncIterator[str]:
        import json

        try:
            async for trendbar in service.stream_trendbars(
                _account_id,
                _symbol,
                _tf,
                _from_ts,
                _to_ts,
                _limit,
            ):
                bar_dict = {
                    "o": float(trendbar.o),
                    "h": float(trendbar.h),
                    "l": float(trendbar.l),
                    "c": float(trendbar.c),
                    "v": trendbar.v,
                    "t": trendbar.t,
                    "digits": trendbar.digits,
                }
                yield json.dumps(bar_dict) + "\n"
        except RuntimeError:
            logger.exception(
                "Trendbar stream interrupted due to upstream request failure "
                "(symbol=%s, timeframe=%s, from_ts=%s, to_ts=%s, limit=%s)",
                _symbol,
                _tf.value,
                _from_ts,
                _to_ts,
                _limit,
            )
            return

    return StreamingResponse(
        generate_ndjson(),
        media_type="application/x-ndjson",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/{symbol}/trendbar-stream/start")
async def start_trendbar_stream(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, Any]:
    tf = timeframe
    normalized_symbol = symbol.upper()

    status = await service.start_trendbar_stream(
        account_id,
        normalized_symbol,
        tf,
    )
    return serialize_trendbar_stream_status(status)


@router.get("/{symbol}/trendbar-stream/stop")
async def stop_trendbar_stream(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, str]:
    tf = timeframe
    normalized_symbol = symbol.upper()
    await service.stop_trendbar_stream(account_id, normalized_symbol, tf)
    return {"status": "stopped", "symbol": normalized_symbol, "timeframe": tf.value}


@router.get("/{symbol}/trendbar-stream/status")
async def trendbar_stream_status(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> dict[str, Any]:
    tf = timeframe
    normalized_symbol = symbol.upper()
    status = await service.trendbar_stream_status(account_id, normalized_symbol, tf)
    return serialize_trendbar_stream_status(status)
