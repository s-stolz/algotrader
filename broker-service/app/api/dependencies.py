from fastapi import Depends, Header, HTTPException, Request

from app.application.services import (
    AccountService,
    MarketDataService,
    OrderService,
    PositionService,
)
from app.domain.value_objects import AccountId
from app.infrastructure.config import ServiceContainer


def get_account_id(
    x_account_id: str | None = Header(default=None, alias="X-Account-Id"),
) -> AccountId:
    """Extract and validate X-Account-Id header."""
    if x_account_id is None:
        raise HTTPException(
            status_code=400,
            detail="X-Account-Id header is required",
        )
    try:
        return AccountId(int(x_account_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="X-Account-Id must be a valid integer",
        ) from exc


def get_container(request: Request) -> ServiceContainer:
    container: ServiceContainer = request.app.state.container
    return container


def get_account_service(container: ServiceContainer = Depends(get_container)) -> AccountService:
    return container.account_service


def get_order_service(container: ServiceContainer = Depends(get_container)) -> OrderService:
    return container.order_service


def get_position_service(container: ServiceContainer = Depends(get_container)) -> PositionService:
    return container.position_service


def get_market_data_service(
    container: ServiceContainer = Depends(get_container),
) -> MarketDataService:
    return container.market_data_service
