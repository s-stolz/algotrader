from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import (
    accounts,
    deals,
    market_data,
    meta,
    orders,
    positions,
)
from app.infrastructure.config import ServiceContainer
from app.infrastructure.logging import configure_logging
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    container = ServiceContainer(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await container.startup()
        yield
        await container.shutdown()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.container = container

    app.include_router(meta.router)
    app.include_router(accounts.router)
    app.include_router(orders.router)
    app.include_router(positions.router)
    app.include_router(deals.router)
    app.include_router(market_data.router)

    return app


app = create_app()


def run() -> None:
    """CLI entry point defined in pyproject scripts."""

    import uvicorn

    container: ServiceContainer = app.state.container
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=container.settings.service_port,
        log_level=container.settings.log_level.lower(),
    )
