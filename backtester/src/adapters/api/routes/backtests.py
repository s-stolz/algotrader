"""Public durable backtest submission and status routes."""

from __future__ import annotations

from typing import Any, Literal

from app.backtest_batches import BacktestBatchService
from app.backtest_queue import BacktestQueueService
from app.backtest_runs import (
    BacktestCandleUnavailableError,
    BacktestRunConflictError,
    BacktestRunNotFoundError,
    BacktestRunPersistenceError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from app.config import BacktesterConfig
from app.sweeps import SweepPreviewService
from db_accessor_client import DatabaseAccessorClient, DatabaseAccessorClientError
from domain.enums import BacktestEngine, BacktestRunStatus
from domain.types import BacktestRunQuery
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from strategies.registry import (
    InvalidParameterCombinationError,
    InvalidStrategyParameterError,
    StrategyVersionUnavailableError,
    strategy_catalog,
)

from adapters.api.schemas import (
    BacktestFillResponseSchema,
    BacktestQueueSnapshotSchema,
    BacktestRunResponseSchema,
    BacktestSubmissionRequestSchema,
    BacktestSubmissionResponseSchema,
    BacktestTradeResponseSchema,
    BatchAcceptanceRequestSchema,
    SweepPreviewRequestSchema,
)
from adapters.persistence import (
    DatabaseAccessorBacktestRunRepository,
    DatabaseAccessorQueueStateReader,
    _run_record_from_response,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])


def get_backtest_run_service() -> BacktestRunService:
    return BacktestRunService(repository=DatabaseAccessorBacktestRunRepository())


def get_backtest_queue_service() -> BacktestQueueService:
    return BacktestQueueService(
        DatabaseAccessorQueueStateReader(),
        stale_after_seconds=BacktesterConfig.from_env().worker_stale_after_seconds,
    )


@router.get("/queue", response_model=BacktestQueueSnapshotSchema)
def get_backtest_queue(
    service: BacktestQueueService = Depends(get_backtest_queue_service),
) -> dict[str, Any]:
    try:
        return service.snapshot()
    except (DatabaseAccessorClientError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Backtest queue snapshot unavailable") from exc


@router.get("/queue/health")
def get_backtest_queue_health(
    service: BacktestQueueService = Depends(get_backtest_queue_service),
) -> dict[str, str]:
    try:
        availability = service.snapshot()["availability"]
    except (DatabaseAccessorClientError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail={"availability": "unknown"}) from exc
    if availability != "healthy":
        raise HTTPException(status_code=503, detail={"availability": availability})
    return {"availability": availability}


def get_sweep_preview_service() -> SweepPreviewService:
    def markets() -> list[dict[str, object]]:
        with DatabaseAccessorClient() as client:
            return client.get_markets()

    return SweepPreviewService(
        markets=markets,
        max_candidate_count=BacktesterConfig.from_env().max_sweep_candidate_count,
    )


def get_backtest_batch_service() -> BacktestBatchService:
    return BacktestBatchService(
        preview=get_sweep_preview_service(), client_factory=DatabaseAccessorClient
    )


@router.get("/capabilities")
def get_backtest_capabilities(
    service: SweepPreviewService = Depends(get_sweep_preview_service),
) -> dict[str, int | bool]:
    return {
        "max_sweep_candidate_count": service.max_candidate_count,
        "batch_acceptance_enabled": True,
    }


@router.post("/batches", status_code=status.HTTP_202_ACCEPTED)
def accept_batch(
    request: BatchAcceptanceRequestSchema,
    response: Response,
    service: BacktestBatchService = Depends(get_backtest_batch_service),
) -> dict[str, object]:
    try:
        batch = service.accept(request.submission_id, request.to_definition())
    except StrategyVersionUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "strategy_version_unavailable",
                "fields": [],
                "message": "Strategy version is unavailable",
            },
        ) from exc
    except (InvalidStrategyParameterError, InvalidParameterCombinationError) as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "fields": exc.fields, "message": str(exc)}
        ) from exc
    except (InvalidBacktestRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_sweep_definition", "fields": [], "message": str(exc)},
        ) from exc
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "submission_id_conflict",
                    "fields": [],
                    "message": "Submission identity conflicts",
                },
            ) from exc
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc
    response.headers["Location"] = f"/backtests/batches/{batch['batch_id']}"
    return {"batch_id": str(batch["batch_id"]), "status": str(batch["status"])}


@router.get("/batches")
def list_batches(
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    with_failed_members: bool | None = None,
    service: BacktestBatchService = Depends(get_backtest_batch_service),
) -> list[dict[str, Any]]:
    try:
        return service.list(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            with_failed_members=with_failed_members,
        )
    except DatabaseAccessorClientError as exc:
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc


@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: str, service: BacktestBatchService = Depends(get_backtest_batch_service)
) -> dict[str, Any]:
    try:
        return service.get(batch_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest batch not found") from exc
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc


@router.get(
    "/batches/{batch_id}/members",
    response_model=list[BacktestRunResponseSchema],
    response_model_exclude_none=True,
)
def get_batch_members(
    batch_id: str, service: BacktestBatchService = Depends(get_backtest_batch_service)
) -> list[BacktestRunResponseSchema]:
    try:
        return [
            BacktestRunResponseSchema.from_domain(_run_record_from_response(member))
            for member in service.members(batch_id)
        ]
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest batch not found") from exc
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc


@router.get("/batches/{batch_id}/events")
def get_batch_events(
    batch_id: str, service: BacktestBatchService = Depends(get_backtest_batch_service)
) -> list[dict[str, Any]]:
    try:
        return service.events(batch_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest batch not found") from exc
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc


class BatchCommandRequest(BaseModel):
    command_id: str = Field(min_length=1, max_length=36)


@router.post("/batches/{batch_id}/{command}")
def control_batch(
    batch_id: str,
    command: Literal["pause", "resume"],
    request: BatchCommandRequest,
    service: BacktestBatchService = Depends(get_backtest_batch_service),
) -> dict[str, Any]:
    try:
        return service.control(batch_id, command, request.command_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code in {404, 409}:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        raise HTTPException(status_code=503, detail="Batch persistence unavailable") from exc


@router.post("/sweeps/preview")
def preview_sweep(
    request: SweepPreviewRequestSchema,
    service: SweepPreviewService = Depends(get_sweep_preview_service),
) -> dict[str, object]:
    try:
        return service.expand(request.to_definition())
    except DatabaseAccessorClientError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "market_catalog_unavailable",
                "message": "Market catalog unavailable",
            },
        ) from exc
    except StrategyVersionUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "strategy_version_unavailable",
                "message": "Strategy version is unavailable",
            },
        ) from exc
    except (InvalidParameterCombinationError, InvalidStrategyParameterError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "fields": exc.fields,
                "message": str(exc),
            },
        ) from exc
    except (InvalidBacktestRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_sweep_definition",
                "fields": [],
                "message": str(exc),
            },
        ) from exc


@router.post(
    "",
    response_model=BacktestSubmissionResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_backtest(
    request: BacktestSubmissionRequestSchema,
    response: Response,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> BacktestSubmissionResponseSchema:
    try:
        run = service.submit(request.to_domain())
    except StrategyVersionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "strategy_version_unavailable",
                "message": "Strategy version is unavailable",
            },
        ) from exc
    except (InvalidParameterCombinationError, InvalidStrategyParameterError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": exc.code, "fields": exc.fields, "message": str(exc)},
        ) from exc
    except (InvalidBacktestRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except BacktestRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc

    response.headers["Location"] = f"/backtests/{run.run_id}"
    return BacktestSubmissionResponseSchema(run_id=run.run_id, status="queued")


@router.get("/strategies")
def list_strategies() -> list[dict[str, object]]:
    return strategy_catalog()


@router.get(
    "",
    response_model=list[BacktestRunResponseSchema],
    response_model_exclude_none=True,
)
def list_backtests(
    status_filter: BacktestRunStatus | None = Query(default=None, alias="status"),
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    engine: BacktestEngine | None = None,
    submitted_from_ms: int | None = None,
    submitted_to_ms: int | None = None,
    membership: Literal["standalone", "batch"] | None = None,
    batch_id: str | None = None,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> list[BacktestRunResponseSchema]:
    query = BacktestRunQuery(
        status=status_filter,
        symbol=symbol,
        timeframe=timeframe,
        strategy_id=strategy,
        engine=engine,
        submitted_from_ms=submitted_from_ms,
        submitted_to_ms=submitted_to_ms,
        membership=membership,
        batch_id=batch_id,
    )
    try:
        return [BacktestRunResponseSchema.from_domain(run) for run in service.list(query)]
    except InvalidBacktestRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (BacktestRunPersistenceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc


@router.get(
    "/{run_id}",
    response_model=BacktestRunResponseSchema,
    response_model_exclude_none=True,
)
def get_backtest(
    run_id: str,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> BacktestRunResponseSchema:
    try:
        run = service.get(run_id)
        return BacktestRunResponseSchema.from_domain(run)
    except BacktestRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found",
        ) from exc
    except (BacktestRunPersistenceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc


@router.post(
    "/{run_id}/cancel",
    response_model=BacktestRunResponseSchema,
    response_model_exclude_none=True,
)
def cancel_backtest(
    run_id: str,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> BacktestRunResponseSchema:
    try:
        return BacktestRunResponseSchema.from_domain(service.cancel(run_id))
    except BacktestRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Backtest run not found") from exc
    except BacktestRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BacktestRunPersistenceError as exc:
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.get("/{run_id}/equity-curve")
def get_backtest_equity_curve(
    run_id: str,
    max_points: int = Query(default=2000, ge=100, le=10000),
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> dict[str, object]:
    try:
        return service.get_equity_curve(run_id, max_points)
    except BacktestRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Backtest run not found") from exc
    except BacktestRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (BacktestCandleUnavailableError, BacktestRunPersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/{run_id}/fills",
    response_model=list[BacktestFillResponseSchema],
)
def get_backtest_fills(
    run_id: str,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> list[BacktestFillResponseSchema]:
    try:
        return [BacktestFillResponseSchema.from_domain(fill) for fill in service.get_fills(run_id)]
    except BacktestRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found",
        ) from exc
    except (BacktestRunPersistenceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc


@router.get(
    "/{run_id}/trades",
    response_model=list[BacktestTradeResponseSchema],
)
def get_backtest_trades(
    run_id: str,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> list[BacktestTradeResponseSchema]:
    try:
        return [
            BacktestTradeResponseSchema.from_domain(trade) for trade in service.get_trades(run_id)
        ]
    except BacktestRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found",
        ) from exc
    except (BacktestRunPersistenceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_backtest(
    run_id: str,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> Response:
    try:
        service.delete(run_id)
    except BacktestRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest run not found",
        ) from exc
    except BacktestRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except BacktestRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
