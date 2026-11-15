from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_account_service, get_container, get_market_data_service
from app.api.service_protocols import AccountServicePort, MarketDataServicePort
from app.domain.value_objects import AccountId
from app.infrastructure.config import ServiceContainer

router = APIRouter(tags=["setup"])


@router.get("/connection")
async def get_connection(
    service: AccountServicePort = Depends(get_account_service),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    configured_id = os.getenv("ACCOUNT_ID", "")
    if not configured_id.isdecimal() or int(configured_id) <= 0:
        raise HTTPException(503, "No broker account is configured")
    environment = container.credentials.host_type
    try:
        accounts = await service.list_accounts()
    except Exception:
        raise HTTPException(503, "Configured broker account could not be verified") from None
    account = next((entry for entry in accounts if str(entry.account_id) == configured_id), None)
    if account is None or account.is_live != (environment == "live"):
        raise HTTPException(503, "Configured broker account is not authorized")
    if not account.broker_name or not account.broker_name.strip():
        raise HTTPException(503, "Broker did not provide an account label")
    return {
        "provider": "ctrader",
        "account_id": configured_id,
        "environment": environment,
        "broker_name": account.broker_name.strip(),
    }


@router.get("/setup/instruments/{broker_symbol_id}")
async def verify_instrument(
    broker_symbol_id: int,
    account_id: str | None = Query(default=None),
    connection: dict[str, str] = Depends(get_connection),
    service: MarketDataServicePort = Depends(get_market_data_service),
) -> dict[str, Any]:
    if account_id is not None and account_id != connection["account_id"]:
        raise HTTPException(409, "Instrument must belong to the configured broker account")
    selected_account = AccountId(int(connection["account_id"]))
    try:
        instruments = await service.list_symbols(selected_account, refresh=True)
        instrument = next(
            (
                item
                for item in instruments
                if item.symbol_id == broker_symbol_id and item.enabled is not False
            ),
            None,
        )
        if instrument is None:
            raise HTTPException(404, "Broker instrument is unavailable")
        details = await service.get_symbol(selected_account, instrument.symbol_name)
        if details.symbol_id != broker_symbol_id or details.symbol_name != instrument.symbol_name:
            raise HTTPException(503, "Broker instrument identity could not be verified")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Broker instrument could not be verified") from None
    return {
        "source_type": "broker",
        "broker_provider": connection["provider"],
        "broker_account_id": connection["account_id"],
        "broker_environment": connection["environment"],
        "broker_symbol_id": broker_symbol_id,
        "symbol": details.symbol_name,
        "exchange": connection["broker_name"],
        "timezone": details.timezone,
        "settlement_currency": details.settlement_currency,
        "market_type": details.market_type,
        "minimum_quantity": details.minimum_quantity,
        "quantity_step": details.quantity_step,
        "min_move": None,
        "suggested_min_move": 10.0**-details.digits,
        "contract_multiplier": None,
    }
