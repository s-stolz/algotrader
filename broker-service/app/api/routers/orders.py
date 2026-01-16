from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_account_id, get_order_service
from app.api.schemas import OrderRequest
from app.application.services import OrderService
from app.domain.value_objects import AccountId, OrderId

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/")
async def place_order(
    order: OrderRequest,
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
):
    payload = order.model_dump(by_alias=True, exclude_none=True)
    return await service.place_order(account_id, payload)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
):
    await service.cancel_order(account_id, OrderId(order_id))
    return {"status": "cancelled", "orderId": order_id}


@router.get("/open")
async def get_open_orders(
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
):
    return await service.get_open_orders(account_id)


@router.get("/history")
async def get_order_history(
    fromTs: int | None = Query(default=None),
    toTs: int | None = Query(default=None),
    account_id: AccountId = Depends(get_account_id),
    service: OrderService = Depends(get_order_service),
):
    return await service.get_order_history(account_id, fromTs, toTs)
