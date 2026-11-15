import os
from datetime import datetime, timezone
from typing import Literal, Optional

from algotrader_logger import RequestLoggingMiddleware, configure_logging, get_logger
from app import backtest_execution, crud, historical_candles, market_cache, recovery
from app.backtest_execution_log import get_execution_log
from app.candle_pages import forward_candles
from app.database import get_db
from app.market_sources import (
    BrokerVerificationUnavailableError,
    MarketSourceConflictError,
    verify_broker_market,
)
from app.schemas import (
    BacktestClosedTradeOut,
    BacktestCommandIn,
    BacktestCommandOut,
    BacktestCreateIn,
    BacktestEventOut,
    BacktestExecutionClaimIn,
    BacktestExecutionFaultIn,
    BacktestExecutionReconcileIn,
    BacktestExecutionReconcileOut,
    BacktestExecutionSettleIn,
    BacktestExecutionSlotOut,
    BacktestFillOut,
    BacktestOut,
    BacktestQueueStateOut,
    BacktestRunMutationOut,
    BacktestRunOut,
    BacktestWorkerHeartbeatIn,
    BacktestWorkerHeartbeatOut,
    CandleBatchIn,
    ExperimentNameUpdateIn,
    HistoricalCandleBatchIn,
    LiveWriteBegin,
    LiveWriteFinish,
    MarketIn,
    RecoveryAdvance,
    RecoveryBegin,
)
from app.timeframes import TimeframeCode, timeframe_to_minutes
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

configure_logging(
    service_name="database-accessor-api",
    level=os.getenv("DATABASE_ACCESSOR_LOG_LEVEL", "INFO"),
    format=os.getenv("DATABASE_ACCESSOR_LOG_FORMAT", "pretty"),
)
logger = get_logger(__name__)

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
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/")
async def root():
    return {"message": "Welcome to the Database Accessor API"}


@app.get("/health")
async def health():
    logger.debug("Health check requested")
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
    try:
        await verify_broker_market(market.model_dump())
        symbol_id = await crud.insert_market(db, market.model_dump())
    except BrokerVerificationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MarketSourceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (IntegrityError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Symbol and exchange already exist or specifications are invalid",
        ) from exc
    await market_cache.refresh_market_cache(db)
    return {"symbol_id": symbol_id, "status": "created"}


@app.put("/markets/id/{symbol_id}")
async def update_market(symbol_id: int, market: MarketIn, db: AsyncSession = Depends(get_db)):
    try:
        updated = await crud.update_market(db, symbol_id, market.model_dump())
    except MarketSourceConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (IntegrityError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Symbol and exchange already exist or specifications are invalid",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Market not found")
    await market_cache.refresh_market_cache(db)
    return {"symbol_id": updated, "status": "updated"}


@app.get("/markets/id/{market_id}")
async def get_market_by_id(market_id: int, db: AsyncSession = Depends(get_db)):
    market = await crud.get_market_by_id(db, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@app.get("/markets/id/{market_id}/coverage")
async def get_market_coverage(market_id: int, db: AsyncSession = Depends(get_db)):
    if await crud.get_market_by_id(db, market_id) is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return await crud.get_market_coverage(db, market_id)


@app.get("/backtest-execution/slot", response_model=BacktestExecutionSlotOut)
async def get_backtest_execution_slot(db: AsyncSession = Depends(get_db)):
    return await backtest_execution.read_slot(db)


@app.get("/backtest-execution/queue-state", response_model=BacktestQueueStateOut)
async def get_backtest_queue_state(db: AsyncSession = Depends(get_db)):
    return await backtest_execution.read_queue_state(db)


@app.post("/backtest-execution/heartbeat", response_model=BacktestWorkerHeartbeatOut)
async def record_backtest_worker_heartbeat(
    heartbeat: BacktestWorkerHeartbeatIn, db: AsyncSession = Depends(get_db)
):
    return await backtest_execution.record_heartbeat(db, **heartbeat.model_dump())


@app.post("/backtest-execution/claim", response_model=BacktestRunMutationOut)
async def claim_backtest_execution(
    claim: BacktestExecutionClaimIn, db: AsyncSession = Depends(get_db)
):
    return {"updated": await backtest_execution.claim(db, **claim.model_dump())}


@app.post("/backtest-execution/settle", response_model=BacktestRunMutationOut)
async def settle_backtest_execution(
    settlement: BacktestExecutionSettleIn, db: AsyncSession = Depends(get_db)
):
    data = settlement.model_dump()
    run_id = data.pop("run_id")
    owner_token = data.pop("owner_token")
    return {
        "updated": await backtest_execution.settle(
            db, run_id=run_id, owner_token=owner_token, terminal=data
        )
    }


@app.post("/backtest-runs/{run_id}/cancel", response_model=BacktestRunOut)
async def cancel_backtest_run(run_id: str, db: AsyncSession = Depends(get_db)):
    outcome = await backtest_execution.cancel_run(
        db, run_id=run_id, requested_at=datetime.now(timezone.utc)
    )
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="Backtest run not found")
    if outcome == "conflict":
        raise HTTPException(status_code=409, detail="Terminal backtest run cannot be cancelled")
    if outcome == "ownership_unconfirmed":
        raise HTTPException(status_code=503, detail="Execution ownership cannot be confirmed")
    return await crud.get_backtest_run(db, run_id)


@app.post("/backtest-execution/reconcile", response_model=BacktestExecutionReconcileOut)
async def reconcile_backtest_execution(
    reconciliation: BacktestExecutionReconcileIn, db: AsyncSession = Depends(get_db)
):
    return {"reconciled": await backtest_execution.reconcile(db, **reconciliation.model_dump())}


@app.post("/backtest-execution/fault", response_model=BacktestRunMutationOut)
async def record_backtest_execution_fault(
    fault: BacktestExecutionFaultIn, db: AsyncSession = Depends(get_db)
):
    return {"updated": await backtest_execution.record_fault(db, **fault.model_dump())}


@app.get("/backtest-runs", response_model=list[BacktestRunOut])
async def list_backtest_runs(
    status: (
        Literal["queued", "running", "cancelling", "succeeded", "failed", "cancelled"] | None
    ) = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    engine: Literal["vectorized", "event_driven"] | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    backtest_id: str | None = None,
    include_diagnostics: bool = True,
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_backtest_runs(
        db,
        status=status,
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        engine=engine,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        backtest_id=backtest_id,
        include_diagnostics=include_diagnostics,
    )


@app.post("/backtests", response_model=BacktestOut, status_code=201)
async def create_backtest(backtest: BacktestCreateIn, db: AsyncSession = Depends(get_db)):
    try:
        return await crud.create_backtest(db, backtest.model_dump())
    except crud.BacktestSubmissionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/backtests", response_model=list[BacktestOut])
async def list_backtests(db: AsyncSession = Depends(get_db)):
    return await crud.list_backtests(db)


@app.patch("/backtests/{backtest_id}/name", response_model=BacktestOut)
async def rename_backtest(
    backtest_id: str, request: ExperimentNameUpdateIn, db: AsyncSession = Depends(get_db)
):
    backtest = await crud.rename_backtest(db, backtest_id, request.name)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest


@app.get("/backtests/{backtest_id}", response_model=BacktestOut)
async def get_backtest(backtest_id: str, db: AsyncSession = Depends(get_db)):
    backtest = await crud.get_backtest(db, backtest_id)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest


@app.get("/backtests/{backtest_id}/members", response_model=list[BacktestRunOut])
async def list_backtest_members(
    backtest_id: str, include_diagnostics: bool = True, db: AsyncSession = Depends(get_db)
):
    if await crud.get_backtest(db, backtest_id) is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return await crud.list_backtest_members(
        db, backtest_id, include_diagnostics=include_diagnostics
    )


@app.get("/backtests/{backtest_id}/events", response_model=list[BacktestEventOut])
async def list_backtest_events(backtest_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest(db, backtest_id) is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return await crud.list_backtest_events(db, backtest_id)


@app.delete("/backtests/{backtest_id}", status_code=204, response_class=Response)
async def delete_backtest(backtest_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        deleted = await crud.delete_backtest(db, backtest_id)
    except crud.BacktestDeletionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return Response(status_code=204)


@app.post("/backtests/{backtest_id}/{command}", response_model=BacktestCommandOut)
async def control_backtest(
    backtest_id: str,
    command: Literal["pause", "resume", "cancel"],
    request: BacktestCommandIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await backtest_execution.control_backtest(
            db,
            backtest_id=backtest_id,
            command=command,
            command_id=request.command_id,
            policy=request.policy.model_dump(),
        )
    except backtest_execution.BacktestCommandConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@app.get("/backtest-runs/{run_id}", response_model=BacktestRunOut)
async def get_backtest_run(
    run_id: str, include_diagnostics: bool = True, db: AsyncSession = Depends(get_db)
):
    run = await crud.get_backtest_run(db, run_id, include_diagnostics=include_diagnostics)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


@app.get("/backtest-runs/{run_id}/execution-log")
async def get_backtest_execution_log(
    run_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    include_unexecuted: bool = False,
    db: AsyncSession = Depends(get_db),
):
    result = await get_execution_log(
        db, run_id, page=page, page_size=page_size, include_unexecuted=include_unexecuted
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return result


@app.get("/backtest-runs/{run_id}/fills", response_model=list[BacktestFillOut])
async def get_backtest_fills(run_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_run(db, run_id) is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return await crud.get_backtest_fills(db, run_id)


@app.get("/backtest-runs/{run_id}/trades", response_model=list[BacktestClosedTradeOut])
async def get_backtest_trades(run_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_run(db, run_id) is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return await crud.get_backtest_trades(db, run_id)


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


@app.get("/candles/{symbol}/stream")
async def stream_candles(
    symbol: str,
    timeframe: TimeframeCode,
    start_ms: int,
    end_ms: int,
    exchange: Optional[str] = None,
    market_id: Optional[int] = Query(None, gt=0),
    db: AsyncSession = Depends(get_db),
):
    from app.candle_stream import candle_messages
    from app.database import AsyncSessionLocal
    from starlette.responses import StreamingResponse

    if start_ms >= end_ms:
        raise HTTPException(status_code=422, detail="start_ms must precede end_ms")
    await market_cache.ensure_market_cache(db)
    symbol_id = (
        market_id
        if isinstance(market_id, int)
        else market_cache.resolve_symbol_id(symbol, exchange)
    )
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return StreamingResponse(
        candle_messages(
            AsyncSessionLocal, symbol_id, timeframe_to_minutes(timeframe), start_ms, end_ms
        ),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/candles/{symbol}")
async def read_aggregated_candles_by_symbol(
    symbol: str,
    market_id: Optional[int] = Query(None, gt=0),
    exchange: Optional[str] = Query(None, description="Market exchange"),
    timeframe: TimeframeCode = Query(..., description="Timeframe code (e.g. M1, H1)"),
    start_ms: Optional[int] = Query(None, description="Start timestamp in epoch ms (UTC)"),
    end_ms: Optional[int] = Query(None, description="End timestamp in epoch ms (UTC)"),
    limit: Optional[int] = Query(None),
    from_start: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    await market_cache.ensure_market_cache(db)
    symbol_id = (
        market_id
        if isinstance(market_id, int)
        else market_cache.resolve_symbol_id(symbol, exchange)
    )
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    if from_start is True:
        if (
            not isinstance(start_ms, int)
            or not isinstance(end_ms, int)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise HTTPException(
                status_code=422,
                detail="Forward pages require start_ms, end_ms and limit between 1 and 500",
            )
        if start_ms >= end_ms:
            raise HTTPException(status_code=422, detail="start_ms must precede end_ms")
        return await forward_candles(
            db, symbol_id, timeframe_to_minutes(timeframe), start_ms, end_ms, limit
        )

    return await crud.get_candles(
        db,
        symbol_id,
        timeframe_to_minutes(timeframe),
        start_ms,
        end_ms,
        limit,
    )


@app.get("/candles/{symbol}/latest")
async def read_latest_candle_by_symbol(
    symbol: str,
    exchange: Optional[str] = Query(None, description="Market exchange"),
    db: AsyncSession = Depends(get_db),
):
    await market_cache.ensure_market_cache(db)
    symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        await market_cache.refresh_market_cache(db)
        symbol_id = market_cache.resolve_symbol_id(symbol, exchange)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")

    candle = await crud.get_latest_m1_candle(db, symbol_id)
    if candle is None:
        raise HTTPException(status_code=404, detail="No candles found")
    return candle


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
        batch = candles[i : i + batch_size]
        added_candles = await crud.insert_candles(db, symbol_id, batch)

        total_added += added_candles

    return {"status": "ok", "added_candles": total_added, "total_candles": len(candles)}


@app.post("/candles/upload")
async def upload_candle_batch(data: CandleBatchIn, db: AsyncSession = Depends(get_db)):
    matches = await crud.get_markets(db, data.symbol, data.exchange)
    if not matches:
        raise HTTPException(status_code=404, detail="Market not found")
    if len(matches) != 1:
        raise HTTPException(status_code=409, detail="Provide an exchange for the uploaded market")
    if matches[0]["source_type"] != "custom":
        raise HTTPException(status_code=409, detail="CSV uploads require a custom market")
    return await insert_candle_batch(data, db)


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


@app.post("/candles/historical")
async def write_historical_candle_batch(
    data: HistoricalCandleBatchIn, db: AsyncSession = Depends(get_db)
):
    open_minute = (int(datetime.now(timezone.utc).timestamp() * 1000) // 60000) * 60000
    if data.end_ms >= open_minute:
        raise HTTPException(status_code=422, detail="Historical interval must exclude open M1")
    await market_cache.ensure_market_cache(db)
    try:
        symbol_id = market_cache.resolve_symbol_id(
            data.symbol, data.exchange, reject_ambiguous=True
        )
        if symbol_id is None:
            await market_cache.refresh_market_cache(db)
            symbol_id = market_cache.resolve_symbol_id(
                data.symbol, data.exchange, reject_ambiguous=True
            )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if symbol_id is None:
        raise HTTPException(status_code=404, detail="Market not found")
    values = [candle.model_dump() for candle in data.candles]
    total = 0
    for offset in range(0, len(values), 4000):
        total += await historical_candles.write_historical_candles(
            db, symbol_id, values[offset : offset + 4000]
        )
    return {"status": "ok", "written_candles": total, "total_candles": len(values)}


@app.get("/recoveries/{symbol_id}")
async def load_pending_recovery(
    symbol_id: int,
    account_id: str = Query(..., min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    return {"pending": await recovery.load_recovery(db, symbol_id, account_id)}


@app.post("/recoveries/begin")
async def begin_pending_recovery(data: RecoveryBegin, db: AsyncSession = Depends(get_db)):
    from app.models import markets
    from sqlalchemy import select

    if (
        await db.scalar(select(markets.c.symbol_id).where(markets.c.symbol_id == data.symbol_id))
        is None
    ):
        raise HTTPException(status_code=404, detail="Market not found")
    open_minute = (int(datetime.now(timezone.utc).timestamp() * 1000) // 60000) * 60000
    if data.target_ms >= open_minute:
        raise HTTPException(status_code=422, detail="Recovery must exclude open M1")
    return await recovery.begin_recovery(db, **data.model_dump())


@app.post("/recoveries/advance")
async def advance_pending_recovery(data: RecoveryAdvance, db: AsyncSession = Depends(get_db)):
    return {"updated": await recovery.advance_recovery(db, data.symbol_id, data.account_id, data)}


@app.get("/recoveries/live-writes/{symbol_id}")
async def load_live_write_guard(
    symbol_id: int,
    account_id: str = Query(..., min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    return {"guard": await recovery.load_live_write_guard(db, symbol_id, account_id)}


@app.post("/recoveries/live-writes/begin")
async def begin_live_write(data: LiveWriteBegin, db: AsyncSession = Depends(get_db)):
    from app.models import markets
    from sqlalchemy import select

    if (
        await db.scalar(select(markets.c.symbol_id).where(markets.c.symbol_id == data.symbol_id))
        is None
    ):
        raise HTTPException(status_code=404, detail="Market not found")
    return await recovery.begin_live_write(db, **data.model_dump())


@app.post("/recoveries/live-writes/finish")
async def finish_live_write(data: LiveWriteFinish, db: AsyncSession = Depends(get_db)):
    return {"updated": await recovery.finish_live_write(db, **data.model_dump())}
