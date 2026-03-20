from __future__ import annotations

from app.schemas_live import (
    LiveIndicatorStartResponse,
    LiveIndicatorStatusResponse,
    LiveIndicatorStopResponse,
    LiveIndicatorStreamRequest,
)
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/indicator-streams", tags=["indicator-streams"])


@router.post("/start", response_model=LiveIndicatorStartResponse)
async def start_live_indicator_stream(
    request: Request,
    payload: LiveIndicatorStreamRequest,
) -> LiveIndicatorStartResponse:
    manager = request.app.state.live_indicator_manager
    try:
        return await manager.start_stream(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/stop", response_model=LiveIndicatorStopResponse)
async def stop_live_indicator_stream(
    request: Request,
    payload: LiveIndicatorStreamRequest,
) -> LiveIndicatorStopResponse:
    manager = request.app.state.live_indicator_manager
    try:
        return await manager.stop_stream(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{stream_id}", response_model=LiveIndicatorStatusResponse)
async def get_live_indicator_stream_status(
    request: Request,
    stream_id: str,
) -> LiveIndicatorStatusResponse:
    manager = request.app.state.live_indicator_manager
    status = await manager.get_status(stream_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    return status
