"""FastAPI application factory for the backtester service."""

from __future__ import annotations

from app.backtest_runs import BacktestRunService
from fastapi import FastAPI

from adapters.api.routes import backtests_router
from adapters.api.routes.backtests import get_backtest_run_service


def create_app(*, service: BacktestRunService | None = None) -> FastAPI:
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

    return app
