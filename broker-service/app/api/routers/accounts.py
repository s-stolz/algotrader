from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_account_service
from app.api.serialization import to_jsonable
from app.application.services import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/")
async def list_accounts(
    service: AccountService = Depends(get_account_service),
) -> list[dict[str, Any]]:
    return to_jsonable(await service.list_accounts())
