"""Public durable backtest submission and status routes."""

from __future__ import annotations

from app.backtest_runs import (
    BacktestRunNotFoundError,
    BacktestRunPersistenceError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status

from adapters.api.schemas import (
    BacktestRunResponseSchema,
    BacktestSubmissionRequestSchema,
    BacktestSubmissionResponseSchema,
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
