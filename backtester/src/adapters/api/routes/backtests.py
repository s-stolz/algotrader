"""Public durable backtest submission and status routes."""

from __future__ import annotations

from app.backtest_runs import (
    BacktestRunConflictError,
    BacktestRunNotFoundError,
    BacktestRunPersistenceError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from domain.enums import BacktestEngine, BacktestRunStatus
from domain.types import BacktestRunQuery
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from adapters.api.schemas import (
    BacktestFillResponseSchema,
    BacktestRunResponseSchema,
    BacktestSubmissionRequestSchema,
    BacktestSubmissionResponseSchema,
    BacktestTradeResponseSchema,
)
from adapters.persistence import DatabaseAccessorBacktestRunRepository

router = APIRouter(prefix="/backtests", tags=["backtests"])


def get_backtest_run_service() -> BacktestRunService:
    return BacktestRunService(repository=DatabaseAccessorBacktestRunRepository())


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
            detail="Only terminal backtest runs can be deleted",
        ) from exc
    except BacktestRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest persistence unavailable",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
