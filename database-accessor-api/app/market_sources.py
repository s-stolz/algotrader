"""Verify broker instrument identity and preserve a Market's original source."""

import os
from typing import Any

import httpx

SOURCE_FIELDS = (
    "source_type",
    "broker_provider",
    "broker_account_id",
    "broker_environment",
    "broker_symbol_id",
)


class MarketSourceConflictError(ValueError):
    pass


class BrokerVerificationUnavailableError(RuntimeError):
    pass


def validate_source_edit(current: dict[str, Any], replacement: dict[str, Any]) -> None:
    for field in SOURCE_FIELDS:
        if current.get(field) != replacement.get(field):
            raise MarketSourceConflictError("Market source cannot change after creation")
    if current["source_type"] == "broker" and any(
        current[field] != replacement[field] for field in ("symbol", "exchange")
    ):
        raise MarketSourceConflictError("Broker instrument cannot change after creation")


async def verify_broker_market(market: dict[str, Any]) -> None:
    if market["source_type"] != "broker":
        return
    account_id = os.getenv("ACCOUNT_ID")
    environment = os.getenv("CTRADER_HOST_TYPE")
    if not account_id or not environment:
        raise BrokerVerificationUnavailableError("Broker connection is not configured")
    if (market["broker_account_id"], market["broker_environment"]) != (
        account_id,
        environment,
    ):
        raise MarketSourceConflictError("Market does not belong to the configured broker account")
    host = os.getenv("BROKER_SERVICE_HOST", "broker-service")
    port = os.getenv("BROKER_SERVICE_PORT", "8050")
    url = f"http://{host}:{port}/setup/instruments/{market['broker_symbol_id']}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params={"account_id": account_id})
            response.raise_for_status()
            verified = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise BrokerVerificationUnavailableError("Could not verify broker instrument") from exc
    if not isinstance(verified, dict):
        raise BrokerVerificationUnavailableError("Broker returned an invalid instrument")
    for field in (*SOURCE_FIELDS, "symbol", "exchange"):
        actual = verified.get(field)
        if field in ("symbol", "exchange") and isinstance(actual, str):
            actual = actual.strip().upper()
        if actual != market[field]:
            raise MarketSourceConflictError(
                "Instrument identity does not match the broker catalogue"
            )
