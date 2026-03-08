from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.contracts import CLOSE_POSITION_REQUEST_SCHEMA
from app.api.dependencies import get_account_id, get_position_service
from app.api.serialization import to_jsonable
from app.api.validation import parse_close_position_request, read_json_body
from app.application.services import PositionService
from app.domain.value_objects import AccountId, PositionId

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/")
async def get_open_positions(
    account_id: AccountId = Depends(get_account_id),
    service: PositionService = Depends(get_position_service),
) -> list[dict[str, Any]]:
    return to_jsonable(await service.get_open_positions(account_id))


@router.post(
    "/{position_id}/close",
    openapi_extra={
        "requestBody": {
            "required": False,
            "content": {
                "application/json": {
                    "schema": CLOSE_POSITION_REQUEST_SCHEMA,
                }
            },
        }
    },
)
async def close_position(
    position_id: int,
    request: Request,
    account_id: AccountId = Depends(get_account_id),
    service: PositionService = Depends(get_position_service),
) -> dict[str, Any]:
    body = {}
    if request.headers.get("content-length") not in {None, "0"}:
        body = await read_json_body(request)

    payload = parse_close_position_request(body)
    close_volume = payload.get("closeQuantity")
    result = await service.close_position(account_id, PositionId(position_id), close_volume)
    return to_jsonable(result)
