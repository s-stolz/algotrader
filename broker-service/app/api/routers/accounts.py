from fastapi import APIRouter, Depends

from app.api.dependencies import get_account_service
from app.application.services import AccountService
from app.domain.models import Account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/")
async def list_accounts(
    service: AccountService = Depends(get_account_service)
) -> list[Account]:
    return await service.list_accounts()
