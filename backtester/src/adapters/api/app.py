"""FastAPI application factory for the backtester service."""

from __future__ import annotations

from asyncio import to_thread
from contextlib import asynccontextmanager

from app.backtest_batches import BacktestBatchService
from app.backtest_queue import BacktestQueueService
from app.backtest_runs import BacktestRunService
from app.sweeps import SweepPreviewService
from fastapi import FastAPI

from adapters.api.routes import backtests_router
from adapters.api.routes.backtests import (
    get_backtest_batch_service,
    get_backtest_queue_service,
    get_backtest_run_service,
    get_sweep_preview_service,
)
from adapters.backtest_events import BacktestEventPublisher


def create_app(
    *,
    events: BacktestEventPublisher | None = None,
    service: BacktestRunService | None = None,
    preview_service: SweepPreviewService | None = None,
    batch_service: BacktestBatchService | None = None,
    queue_service: BacktestQueueService | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if events is not None:
            events.start()
        try:
            yield
        finally:
            if events is not None:
                await to_thread(events.close)

    app = FastAPI(
        lifespan=lifespan,
        title="Backtester API",
        description="Durable asynchronous backtest submission and status API",
    )

    if events is not None:
        app.middleware("http")(_publication_middleware(events))

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
    if queue_service is not None:
        app.dependency_overrides[get_backtest_queue_service] = lambda: queue_service

    return app


def _publication_middleware(events: BacktestEventPublisher):
    async def publish_changes(request, call_next):
        try:
            return await call_next(request)
        finally:
            # Error responses can follow an ambiguous storage commit; invalidation
            # is harmless for rejected or no-op commands.
            if (
                request.method in {"POST", "PATCH", "PUT", "DELETE"}
                and request.url.path.startswith("/backtests")
                and not request.url.path.endswith("/preview")
            ):
                events.changed()

    return publish_changes
