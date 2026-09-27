import os
from datetime import datetime, timezone
from typing import Literal, Optional

from algotrader_logger import RequestLoggingMiddleware, configure_logging, get_logger
from app import backtest_execution, crud, market_cache
from app.database import get_db
from app.schemas import (
    BacktestBatchCommandIn,
    BacktestBatchCommandOut,
    BacktestBatchCreateIn,
    BacktestBatchEventOut,
    BacktestBatchOut,
    BacktestClosedTradeOut,
    BacktestExecutionClaimIn,
    BacktestExecutionFaultIn,
    BacktestExecutionReconcileIn,
    BacktestExecutionReconcileOut,
    BacktestExecutionSettleIn,
    BacktestExecutionSlotOut,
    BacktestFillOut,
    BacktestQueueStateOut,
    BacktestRunCompleteIn,
    BacktestRunConditionalUpdateIn,
    BacktestRunCreateIn,
    BacktestRunMutationOut,
    BacktestRunOut,
    BacktestWorkerHeartbeatIn,
    BacktestWorkerHeartbeatOut,
    CandleBatchIn,
    MarketIn,
)
from app.timeframes import TimeframeCode, timeframe_to_minutes
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
    symbol_id = await crud.insert_market(db, market.model_dump())
    await market_cache.refresh_market_cache(db)
    return {"symbol_id": symbol_id, "status": "created"}


@app.post("/backtests", response_model=BacktestRunOut, status_code=201)
async def create_backtest_run(
    run: BacktestRunCreateIn,
    db: AsyncSession = Depends(get_db),
):
    payload = run.model_dump()
    if run.request_schema_version == 2:
        payload["request"]["strategy"].pop("strategy_version", None)
    return await crud.insert_backtest_run(db, payload)


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


@app.post("/backtests/{run_id}/cancel", response_model=BacktestRunOut)
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


@app.get("/backtests", response_model=list[BacktestRunOut])
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
    membership: Literal["standalone", "batch"] | None = None,
    batch_id: str | None = None,
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
        membership=membership,
        batch_id=batch_id,
    )


@app.post("/backtest-batches", response_model=BacktestBatchOut, status_code=201)
async def create_backtest_batch(batch: BacktestBatchCreateIn, db: AsyncSession = Depends(get_db)):
    try:
        return await crud.create_backtest_batch(db, batch.model_dump())
    except crud.BatchSubmissionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/backtest-batches", response_model=list[BacktestBatchOut])
async def list_backtest_batches(db: AsyncSession = Depends(get_db)):
    return await crud.list_backtest_batches(db)


@app.get("/backtest-batches/{batch_id}", response_model=BacktestBatchOut)
async def get_backtest_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    batch = await crud.get_backtest_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Backtest batch not found")
    return batch


@app.get("/backtest-batches/{batch_id}/members", response_model=list[BacktestRunOut])
async def list_backtest_batch_members(batch_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_batch(db, batch_id) is None:
        raise HTTPException(status_code=404, detail="Backtest batch not found")
    return await crud.list_backtest_batch_members(db, batch_id)


@app.get("/backtest-batches/{batch_id}/events", response_model=list[BacktestBatchEventOut])
async def list_backtest_batch_events(batch_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_batch(db, batch_id) is None:
        raise HTTPException(status_code=404, detail="Backtest batch not found")
    return await crud.list_backtest_batch_events(db, batch_id)


@app.post("/backtest-batches/{batch_id}/{command}", response_model=BacktestBatchCommandOut)
async def control_backtest_batch(
    batch_id: str,
    command: Literal["pause", "resume", "cancel"],
    request: BacktestBatchCommandIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await backtest_execution.control_batch(
            db,
            batch_id=batch_id,
            command=command,
            command_id=request.command_id,
            policy=request.policy.model_dump(),
        )
    except backtest_execution.BatchCommandConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest batch not found")
    return result


@app.get("/backtests/{run_id}", response_model=BacktestRunOut)
async def get_backtest_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await crud.get_backtest_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


@app.get("/backtests/{run_id}/fills", response_model=list[BacktestFillOut])
async def get_backtest_fills(run_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_run(db, run_id) is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return await crud.get_backtest_fills(db, run_id)


@app.get("/backtests/{run_id}/trades", response_model=list[BacktestClosedTradeOut])
async def get_backtest_trades(run_id: str, db: AsyncSession = Depends(get_db)):
    if await crud.get_backtest_run(db, run_id) is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return await crud.get_backtest_trades(db, run_id)


@app.delete("/backtests/{run_id}", status_code=204, response_class=Response)
async def delete_backtest_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    run = await crud.get_backtest_run(db, run_id)
    if run is not None and run["batch_id"] is not None:
        raise HTTPException(status_code=409, detail="Batch members cannot be deleted individually")
    deleted = await crud.delete_backtest_run(db, run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return Response(status_code=204)


@app.patch("/backtests/{run_id}", response_model=BacktestRunMutationOut)
async def conditional_update_backtest_run(
    run_id: str,
    update: BacktestRunConditionalUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    update_data = update.model_dump(exclude_unset=True)
    expected_status = update_data.pop("expected_status")
    update_data["status"] = update_data.pop("new_status")
    updated = await crud.conditional_update_backtest_run(
        db,
        run_id=run_id,
        expected_status=expected_status,
        updates=update_data,
    )
    return {"updated": updated}


@app.post(
    "/backtests/{run_id}/complete",
    response_model=BacktestRunMutationOut,
)
async def complete_backtest_run(
    run_id: str,
    completion: BacktestRunCompleteIn,
    db: AsyncSession = Depends(get_db),
):
    completion_data = completion.model_dump()
    expected_status = completion_data.pop("expected_status")
    updated = await crud.complete_backtest_run(
        db,
        run_id=run_id,
        expected_status=expected_status,
        completion=completion_data,
    )
    return {"updated": updated}


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
