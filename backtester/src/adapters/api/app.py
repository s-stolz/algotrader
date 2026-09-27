"""FastAPI application factory for the backtester service."""

from __future__ import annotations

from app.backtest_batches import BacktestBatchService
from app.backtest_runs import BacktestRunService
from app.sweeps import SweepPreviewService
from fastapi import FastAPI

from adapters.api.routes import backtests_router
from adapters.api.routes.backtests import (
    get_backtest_batch_service,
    get_backtest_run_service,
    get_sweep_preview_service,
)


def create_app(
    *,
    service: BacktestRunService | None = None,
    preview_service: SweepPreviewService | None = None,
    batch_service: BacktestBatchService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Backtester API",
        description="Durable asynchronous backtest submission and status API",
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(backtests_router)

    if service is not None:
        app.dependency_overrides[get_backtest_run_service] = lambda: service
    if preview_service is not None:
        app.dependency_overrides[get_sweep_preview_service] = lambda: preview_service
    if batch_service is not None:
        app.dependency_overrides[get_backtest_batch_service] = lambda: batch_service

    return app
