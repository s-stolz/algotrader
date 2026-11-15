from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from db_accessor_client import DatabaseAccessorClientError
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.history.models import HistoryRequest, public_snapshot
from app.history.service import HistoryDownloads

if TYPE_CHECKING:
    from main import IngestionService


async def storage_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DatabaseAccessorClientError)
    status = exc.status_code if exc.status_code in {400, 404, 409, 422} else 503
    detail = {
        400: "Invalid historical download request",
        404: "Market or download was not found",
        409: "The market already has an active download or the request no longer applies",
        422: "The requested history must extend before the oldest stored candle",
        503: "History storage is unavailable; try again shortly",
    }[status]
    return JSONResponse(status_code=status, content={"detail": detail})


async def source_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def create_app(service: IngestionService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(service.run())
        try:
            yield
        finally:
            await service.shutdown()
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="Market ingestion", lifespan=lifespan)

    def history() -> HistoryDownloads:
        if service.history is None or not service.ready.is_set():
            raise HTTPException(503, "Ingestion is starting; try again shortly")
        return service.history

    app.add_exception_handler(DatabaseAccessorClientError, storage_error)
    app.add_exception_handler(ValueError, source_error)

    @app.get("/health")
    async def health():
        ready = service.ready.is_set() and not service._shutdown
        return JSONResponse(status_code=200 if ready else 503, content={"ready": ready})

    @app.post("/history-downloads", status_code=201)
    async def create(request: HistoryRequest):
        return public_snapshot(await history().create(request))

    @app.get("/history-downloads")
    async def list_downloads(market_id: Annotated[int, Query(gt=0)]):
        jobs = await history().store.list_history_download_jobs(market_id=market_id)
        return [public_snapshot(job) for job in jobs]

    @app.get("/history-downloads/{job_id}")
    async def get_download(job_id: UUID):
        return public_snapshot(await history().store.get_history_download_job(str(job_id)))

    @app.post("/history-downloads/{job_id}/cancel")
    async def cancel(job_id: UUID):
        return public_snapshot(await history().cancel(str(job_id)))

    @app.post("/history-downloads/{job_id}/retry")
    async def retry(job_id: UUID):
        return public_snapshot(await history().retry(str(job_id)))

    return app
