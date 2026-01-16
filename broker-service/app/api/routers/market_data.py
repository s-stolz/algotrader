from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_account_id, get_market_data_service
from app.api.schemas import (
    SymbolResponse,
    SymbolLightResponse,
    TickStreamRequest,
    TickStreamStatusResponse,
    TrendbarResponse,
    TrendbarStreamStatusResponse,
)
from app.application.services import MarketDataService
from app.domain.models import Symbol
from app.domain.value_objects import (
    AccountId,
    TickStreamOptions,
    Timeframe,
)

router = APIRouter(
    prefix="/symbols",
    tags=["market-data"]
)


def _options_from_request(
        payload: TickStreamRequest | None
) -> TickStreamOptions:
    if payload is None:
        return TickStreamOptions()
    return payload.as_options()


def _serialize_status(status) -> TickStreamStatusResponse:
    return TickStreamStatusResponse(
        running=status.running,
        startedAt=status.started_at,
        lastTickAt=status.last_tick_at,
        uptimeSeconds=status.uptime_seconds,
        error=status.error,
    )


def _serialize_trendbar_status(status) -> TrendbarStreamStatusResponse:
    return TrendbarStreamStatusResponse(
        running=status.running,
        startedAt=status.started_at,
        lastBarAt=status.last_bar_at,
        uptimeSeconds=status.uptime_seconds,
        error=status.error,
    )


@router.get("/", response_model=list[SymbolLightResponse])
async def list_symbols(
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> list[SymbolLightResponse]:
    symbols = await service.list_symbols(account_id)
    return [
        SymbolLightResponse(
            symbolId=int(symbol.symbol_id),
            symbolName=symbol.symbol_name,
            enabled=symbol.enabled,
        )
        for symbol in symbols
    ]


@router.get("/{symbol}", response_model=SymbolResponse)
async def get_symbol(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
) -> Symbol:
    symbol_info = await service.get_symbol(account_id, symbol.upper())
    if symbol_info is None:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return symbol_info


@router.get("/{symbol}/tick-stream/start")
async def start_tick_stream(
    symbol: str,
    payload: TickStreamRequest | None = None,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    status = await service.start_tick_stream(
        account_id,
        symbol.upper(),
        _options_from_request(payload),
    )
    return _serialize_status(status)


@router.get("/{symbol}/tick-stream/stop")
async def stop_tick_stream(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    await service.stop_tick_stream(account_id, symbol.upper())
    return {"status": "stopped", "symbol": symbol.upper()}


@router.get("/{symbol}/tick-stream/status")
async def tick_stream_status(
    symbol: str,
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    status = await service.tick_stream_status(
        account_id,
        symbol.upper()
    )
    return _serialize_status(status)


@router.get("/{symbol}/trendbars", response_model=list[TrendbarResponse])
async def get_trendbars(
        symbol: str,
        timeframe: Timeframe = Query(
            ...,
            description="Timeframe enum, e.g. M1, H1"
        ),
        from_ts: int = Query(
            default=0,
            alias="fromTs",
            description="From timestamp (epoch millis)"
        ),
        to_ts: int | None = Query(
            default=2147483646000,
            alias="toTs",
            description="To timestamp (epoch millis)"
        ),
        limit: int | None = Query(default=None, ge=1, le=1000),
        account_id: AccountId = Depends(get_account_id),
        service: MarketDataService = Depends(get_market_data_service),
):
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await service.get_trendbars(
        account_id,
        symbol.upper(),
        tf,
        from_ts,
        to_ts,
        limit,
    )


@router.get("/{symbol}/trendbar-stream/start")
async def start_trendbar_stream(
    symbol: str,
    timeframe: Timeframe = Query(
        ...,
        description="Timeframe enum, e.g. M1, H1"
    ),
    only_completed_bars: bool = Query(
        default=True,
        alias="onlyCompletedBars",
        description="If true (default), only publish bars when they close. If false, publish every live update.",
    ),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from app.domain.value_objects import TrendbarStreamOptions
    options = TrendbarStreamOptions(only_completed_bars=only_completed_bars)

    status = await service.start_trendbar_stream(
        account_id,
        symbol.upper(),
        tf,
        options,
    )
    return _serialize_trendbar_status(status)


@router.get("/{symbol}/trendbar-stream/stop")
async def stop_trendbar_stream(
    symbol: str,
    timeframe: Timeframe = Query(
        ...,
        description="Timeframe enum, e.g. M1, H1"
    ),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await service.stop_trendbar_stream(
        account_id,
        symbol.upper(),
        tf
    )
    return {
        "status": "stopped",
        "symbol": symbol.upper(),
        "timeframe": tf.value
    }


@router.get("/{symbol}/trendbar-stream/status")
async def trendbar_stream_status(
    symbol: str,
    timeframe: Timeframe = Query(
        ...,
        description="Timeframe enum, e.g. M1, H1"
    ),
    account_id: AccountId = Depends(get_account_id),
    service: MarketDataService = Depends(get_market_data_service),
):
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status = await service.trendbar_stream_status(
        account_id,
        symbol.upper(),
        tf
    )
    return _serialize_trendbar_status(status)
