from __future__ import annotations

import logging
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.contracts import SymbolLightBody, TickStreamStatusBody, TrendbarStreamStatusBody
from app.api.dependencies import get_account_id, get_market_data_service
from app.api.serialization import (
    serialize_symbol,
    serialize_symbol_light,
    serialize_tick_stream_status,
    serialize_trendbar_stream_status,
)
from app.api.service_protocols import MarketDataServicePort
from app.api.validation import parse_tick_stream_body, read_json_body
from app.domain.instrument_binding import BrokerInstrumentMismatchError
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
    service: MarketDataServicePort = Depends(get_market_data_service),
) -> list[SymbolLightBody]:
    symbols = await service.list_symbols(account_id)
    return [serialize_symbol_light(symbol) for symbol in symbols]


@router.get("/{symbol}")
async def get_symbol(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
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
    queue_size: int | None = Query(default=None, ge=1, alias="queueSize"),
    max_stream_length: int | None = Query(default=None, ge=100, alias="maxStreamLength"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
    expected_symbol_id: Annotated[int | None, Query(gt=0)] = None,
) -> TickStreamStatusBody:
    normalized_symbol = symbol.upper()
    body_values: tuple[int | None, int | None] | None = None
    if request.headers.get("content-length") not in {None, "0"}:
        body_values = parse_tick_stream_body(await read_json_body(request))

    try:
        status = await service.start_tick_stream(
            account_id,
            normalized_symbol,
            _options_from_inputs(queue_size, max_stream_length, body_values),
            expected_symbol_id,
        )
    except BrokerInstrumentMismatchError as exc:
        raise HTTPException(409, str(exc)) from exc
    return serialize_tick_stream_status(status)


@router.get("/{symbol}/tick-stream/stop")
async def stop_tick_stream(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
    expected_symbol_id: Annotated[int | None, Query(gt=0)] = None,
) -> dict[str, str]:
    normalized_symbol = symbol.upper()
    try:
        await service.stop_tick_stream(account_id, normalized_symbol, expected_symbol_id)
    except BrokerInstrumentMismatchError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "stopped", "symbol": normalized_symbol}


@router.get("/{symbol}/tick-stream/status")
async def tick_stream_status(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
) -> TickStreamStatusBody:
    normalized_symbol = symbol.upper()
    status = await service.tick_stream_status(account_id, normalized_symbol)
    return serialize_tick_stream_status(status)


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
    service: MarketDataServicePort = Depends(get_market_data_service),
    expected_symbol_id: Annotated[int | None, Query(gt=0)] = None,
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

        count = 0
        try:
            async for trendbar in service.stream_trendbars(
                _account_id,
                _symbol,
                _tf,
                _from_ts,
                _to_ts,
                _limit,
                expected_symbol_id,
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
                count += 1
                yield json.dumps(bar_dict) + "\n"
            yield (
                json.dumps(
                    {
                        "type": "complete",
                        "version": 1,
                        "count": count,
                        "fromTs": _from_ts,
                        "toTs": _to_ts,
                        "limit": _limit,
                    }
                )
                + "\n"
            )
        except Exception:
            logger.exception(
                "Trendbar stream interrupted due to upstream request failure "
                "(symbol=%s, timeframe=%s, from_ts=%s, to_ts=%s, limit=%s)",
                _symbol,
                _tf.value,
                _from_ts,
                _to_ts,
                _limit,
                expected_symbol_id,
            )
            yield json.dumps({"type": "error", "message": "Historical download failed"}) + "\n"

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
    service: MarketDataServicePort = Depends(get_market_data_service),
    expected_symbol_id: Annotated[int | None, Query(gt=0)] = None,
) -> TrendbarStreamStatusBody:
    tf = timeframe
    normalized_symbol = symbol.upper()

    try:
        status = await service.start_trendbar_stream(
            account_id, normalized_symbol, tf, expected_symbol_id
        )
    except BrokerInstrumentMismatchError as exc:
        raise HTTPException(409, str(exc)) from exc
    return serialize_trendbar_stream_status(status)


@router.get("/{symbol}/trendbar-stream/stop")
async def stop_trendbar_stream(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
    expected_symbol_id: Annotated[int | None, Query(gt=0)] = None,
) -> dict[str, str]:
    tf = timeframe
    normalized_symbol = symbol.upper()
    try:
        await service.stop_trendbar_stream(account_id, normalized_symbol, tf, expected_symbol_id)
    except BrokerInstrumentMismatchError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "stopped", "symbol": normalized_symbol, "timeframe": tf.value}


@router.get("/{symbol}/trendbar-stream/status")
async def trendbar_stream_status(
    symbol: str,
    timeframe: Timeframe = Query(..., description="Timeframe enum, e.g. M1, H1"),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataServicePort = Depends(get_market_data_service),
) -> TrendbarStreamStatusBody:
    tf = timeframe
    normalized_symbol = symbol.upper()
    status = await service.trendbar_stream_status(account_id, normalized_symbol, tf)
    return serialize_trendbar_stream_status(status)
