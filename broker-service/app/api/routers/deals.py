from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_account_id, get_position_service
from app.api.serialization import to_jsonable
from app.application.services import PositionService
from app.domain.value_objects import AccountId

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/history")
async def get_deal_history(
    from_ts: int | None = Query(default=None, alias="fromTs"),
    to_ts: int | None = Query(default=None, alias="toTs"),
    account_id: AccountId = Depends(get_account_id),
    service: PositionService = Depends(get_position_service),
) -> list[dict[str, Any]]:
    return to_jsonable(await service.get_deal_history(account_id, from_ts, to_ts))
