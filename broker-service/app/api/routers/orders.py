from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.contracts import ORDER_REQUEST_SCHEMA
from app.api.dependencies import get_account_id, get_order_service
from app.api.serialization import to_jsonable
from app.api.validation import parse_order_request, read_json_body
from app.application.services import OrderService
from app.domain.value_objects import AccountId, OrderId

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "/",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ORDER_REQUEST_SCHEMA,
                }
            },
        }
    },
)
async def place_order(
    request: Request,
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
) -> dict[str, Any]:
    body = await read_json_body(request)
    payload = parse_order_request(body)
    return await service.place_order(account_id, payload)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
) -> dict[str, int | str]:
    await service.cancel_order(account_id, OrderId(order_id))
    return {"status": "cancelled", "orderId": order_id}


@router.get("/open")
async def get_open_orders(
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
) -> list[dict[str, Any]]:
    return to_jsonable(await service.get_open_orders(account_id))


@router.get("/history")
async def get_order_history(
    fromTs: int | None = Query(default=None),
    toTs: int | None = Query(default=None),
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
) -> list[dict[str, Any]]:
    return to_jsonable(await service.get_order_history(account_id, fromTs, toTs))
