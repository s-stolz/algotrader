"""Public durable backtest submission and status routes."""

from __future__ import annotations

from typing import Any, Literal

from app.backtest_definitions import BacktestPreviewService
from app.backtest_queue import BacktestQueueService
from app.backtest_runs import (
    BacktestCandleUnavailableError,
    BacktestRunConflictError,
    BacktestRunNotFoundError,
    BacktestRunPersistenceError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from app.backtests import BacktestService
from app.config import BacktesterConfig
from app.execution_log import ExecutionLogService
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

from adapters.api.execution_log import ExecutionLogPageSchema, get_execution_log_service
from adapters.api.schemas import (
    BacktestFillResponseSchema,
    BacktestNameResponseSchema,
    BacktestPreviewRequestSchema,
    BacktestQueueSnapshotSchema,
    BacktestRunResponseSchema,
    BacktestSubmissionRequestSchema,
    BacktestTradeResponseSchema,
    ExperimentNameUpdateSchema,
)
from adapters.persistence import (
    DatabaseAccessorBacktestRunRepository,
    DatabaseAccessorQueueStateReader,
    _run_record_from_response,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])


def get_backtest_run_service(include_diagnostics: bool = True) -> BacktestRunService:
    return BacktestRunService(
        repository=DatabaseAccessorBacktestRunRepository(include_diagnostics=include_diagnostics)
    )


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


def get_backtest_preview_service() -> BacktestPreviewService:
    def markets() -> list[dict[str, object]]:
        with DatabaseAccessorClient() as client:
            return client.get_markets()

    return BacktestPreviewService(
        markets=markets,
        max_candidate_count=BacktesterConfig.from_env().max_backtest_candidate_count,
    )


def get_backtest_service() -> BacktestService:
    return BacktestService(
        preview=get_backtest_preview_service(), client_factory=DatabaseAccessorClient
    )


@router.get("/capabilities")
def get_backtest_capabilities(
    service: BacktestPreviewService = Depends(get_backtest_preview_service),
) -> dict[str, int | bool]:
    return {
        "max_backtest_candidate_count": service.max_candidate_count,
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def accept_backtest(
    request: BacktestSubmissionRequestSchema,
    response: Response,
    service: BacktestService = Depends(get_backtest_service),
) -> dict[str, object]:
    try:
        backtest = service.accept(request.submission_id, request.to_definition(), name=request.name)
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
            detail={"code": "invalid_backtest_definition", "fields": [], "message": str(exc)},
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
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc
    response.headers["Location"] = f"/backtests/{backtest['backtest_id']}"
    return {"backtest_id": str(backtest["backtest_id"]), "status": str(backtest["status"])}


@router.get("")
def list_backtests(
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    with_failed_members: bool | None = None,
    service: BacktestService = Depends(get_backtest_service),
) -> list[dict[str, Any]]:
    try:
        return service.list(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            with_failed_members=with_failed_members,
        )
    except DatabaseAccessorClientError as exc:
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.patch("/{backtest_id}/name", response_model=BacktestNameResponseSchema)
def rename_backtest(
    backtest_id: str,
    request: ExperimentNameUpdateSchema,
    service: BacktestService = Depends(get_backtest_service),
) -> dict[str, Any]:
    try:
        backtest = service.rename(backtest_id, request.name)
        return {"backtest_id": backtest["backtest_id"], "name": backtest["name"]}
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest not found") from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.get("/strategies")
def list_strategies() -> list[dict[str, object]]:
    return strategy_catalog()


@router.get(
    "/runs",
    response_model=list[BacktestRunResponseSchema],
    response_model_exclude_none=True,
)
def list_backtest_runs(
    status_filter: BacktestRunStatus | None = Query(default=None, alias="status"),
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    engine: BacktestEngine | None = None,
    submitted_from_ms: int | None = None,
    submitted_to_ms: int | None = None,
    backtest_id: str | None = None,
    include_diagnostics: bool = True,
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
        backtest_id=backtest_id,
    )
    try:
        return [
            BacktestRunResponseSchema.from_domain(run, include_diagnostics=include_diagnostics)
            for run in service.list(query)
        ]
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


@router.get("/{backtest_id}")
def get_backtest(
    backtest_id: str, service: BacktestService = Depends(get_backtest_service)
) -> dict[str, Any]:
    try:
        return service.get(backtest_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest not found") from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.get(
    "/{backtest_id}/runs",
    response_model=list[BacktestRunResponseSchema],
    response_model_exclude_none=True,
)
def get_backtest_members(
    backtest_id: str,
    include_diagnostics: bool = True,
    service: BacktestService = Depends(get_backtest_service),
) -> list[BacktestRunResponseSchema]:
    try:
        return [
            BacktestRunResponseSchema.from_domain(
                _run_record_from_response(member), include_diagnostics=include_diagnostics
            )
            for member in service.members(backtest_id, include_diagnostics=include_diagnostics)
        ]
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest not found") from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.get("/{backtest_id}/events")
def get_backtest_events(
    backtest_id: str, service: BacktestService = Depends(get_backtest_service)
) -> list[dict[str, Any]]:
    try:
        return service.events(backtest_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest not found") from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.delete("/{backtest_id}", status_code=204, response_class=Response)
def delete_backtest(
    backtest_id: str, service: BacktestService = Depends(get_backtest_service)
) -> Response:
    try:
        service.delete(backtest_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Backtest not found") from exc
        if exc.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail="Cancel and settle the backtest and all members before deleting it",
            ) from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc
    return Response(status_code=204)


class BacktestCommandRequest(BaseModel):
    command_id: str = Field(min_length=1, max_length=36)


@router.post("/{backtest_id}/{command}")
def control_backtest(
    backtest_id: str,
    command: Literal["pause", "resume", "cancel"],
    request: BacktestCommandRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> dict[str, Any]:
    try:
        return service.control(backtest_id, command, request.command_id)
    except DatabaseAccessorClientError as exc:
        if exc.status_code in {404, 409}:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.post("/preview")
def preview_backtest(
    request: BacktestPreviewRequestSchema,
    service: BacktestPreviewService = Depends(get_backtest_preview_service),
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
                "code": "invalid_backtest_definition",
                "fields": [],
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/runs/{run_id}",
    response_model=BacktestRunResponseSchema,
    response_model_exclude_none=True,
)
def get_backtest_run(
    run_id: str,
    include_diagnostics: bool = True,
    service: BacktestRunService = Depends(get_backtest_run_service),
) -> BacktestRunResponseSchema:
    try:
        run = service.get(run_id)
        return BacktestRunResponseSchema.from_domain(run, include_diagnostics=include_diagnostics)
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
    "/runs/{run_id}/cancel",
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


@router.get("/runs/{run_id}/equity-curve")
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


@router.get("/runs/{run_id}/execution-log", response_model=ExecutionLogPageSchema)
def get_backtest_execution_log(
    run_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    include_unexecuted: bool = False,
    service: ExecutionLogService = Depends(get_execution_log_service),
) -> dict[str, Any]:
    try:
        return service.get_page(run_id, page, page_size, include_unexecuted)
    except BacktestRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Backtest run not found") from exc
    except BacktestRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (BacktestRunPersistenceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Backtest persistence unavailable") from exc


@router.get(
    "/runs/{run_id}/fills",
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
    "/runs/{run_id}/trades",
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
