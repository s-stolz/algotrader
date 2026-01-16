from fastapi import APIRouter, Depends

from app.api.dependencies import get_account_id, get_position_service
from app.api.schemas import ClosePositionRequest
from app.application.services import PositionService
from app.domain.value_objects import AccountId, PositionId

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/")
async def get_open_positions(
    account_id: AccountId = Depends(get_account_id),
    service: PositionService = Depends(get_position_service),
):
    return await service.get_open_positions(account_id)


@router.post("/{position_id}/close")
async def close_position(
    position_id: int,
    payload: ClosePositionRequest,
    account_id: AccountId = Depends(get_account_id),
    service: PositionService = Depends(get_position_service),
):
    close_volume = payload.close_quantity
    return await service.close_position(account_id, PositionId(position_id), close_volume)
