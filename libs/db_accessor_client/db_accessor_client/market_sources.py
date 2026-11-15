"""Resolve stored Markets before acquiring broker-backed live sources."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .client import AsyncDatabaseAccessorClient


def require_broker_market(
    market: Mapping[str, Any], account_id: str, environment: str
) -> dict[str, Any]:
    if market.get("source_type") != "broker":
        raise ValueError("Custom markets do not support broker data")
    if (
        not account_id
        or environment not in {"demo", "live"}
        or market.get("broker_provider") != "ctrader"
        or str(market.get("broker_account_id")) != account_id
        or market.get("broker_environment") != environment
    ):
        raise ValueError("Market does not belong to the connected broker account")
    for field in ("symbol_id", "broker_symbol_id"):
        value = market.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"Market has an invalid {field}")
    if not market.get("symbol") or not market.get("exchange"):
        raise ValueError("Market has no instrument identity")
    return dict(market)


def resolve_broker_dependencies(
    markets: Sequence[Mapping[str, Any]],
    symbols: Sequence[str],
    chart_market: Mapping[str, Any],
    account_id: str,
    environment: str,
) -> list[dict[str, Any]]:
    chart = require_broker_market(chart_market, account_id, environment)
    resolved = []
    for symbol in dict.fromkeys(symbol.upper() for symbol in symbols):
        candidates = []
        for market in markets:
            if (
                str(market.get("symbol", "")).upper() != symbol
                or market.get("exchange") != chart["exchange"]
            ):
                continue
            try:
                candidates.append(require_broker_market(market, account_id, environment))
            except ValueError:
                continue
        if len(candidates) != 1:
            raise ValueError(f"Live input {symbol} requires one connected broker market")
        resolved.append(candidates[0])
    return resolved


class BrokerMarketResolver:
    def __init__(self, account_id: str, environment: str):
        self.account_id = account_id
        self.environment = environment
        host = os.getenv("BROKER_SERVICE_HOST", "broker-service")
        port = os.getenv("BROKER_SERVICE_PORT", "8080")
        self.broker_url = os.getenv("BROKER_SERVICE_BASE_URL", f"http://{host}:{port}").rstrip("/")

    async def resolve(self, market_id: int) -> dict[str, Any]:
        market = await self.resolve_stored(market_id)
        await self.verify([market])
        return market

    async def resolve_stored(self, market_id: int) -> dict[str, Any]:
        if isinstance(market_id, bool) or not isinstance(market_id, int) or market_id <= 0:
            raise ValueError("A positive market_id is required")
        async with AsyncDatabaseAccessorClient() as client:
            market = await client.get_market_by_id(market_id)
        return require_broker_market(market, self.account_id, self.environment)

    async def dependencies(
        self, chart_market: Mapping[str, Any], symbols: Sequence[str]
    ) -> list[dict[str, Any]]:
        if not symbols:
            resolved = [require_broker_market(chart_market, self.account_id, self.environment)]
        else:
            async with AsyncDatabaseAccessorClient() as client:
                markets = await client.get_markets(exchange=str(chart_market["exchange"]))
            resolved = resolve_broker_dependencies(
                markets, symbols, chart_market, self.account_id, self.environment
            )
        await self.verify(resolved)
        return resolved

    async def verify(self, markets: Sequence[Mapping[str, Any]]) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            for market in markets:
                response = await client.get(
                    f"{self.broker_url}/setup/instruments/{market['broker_symbol_id']}",
                    params={"account_id": self.account_id},
                )
                response.raise_for_status()
                actual = response.json()
                if not isinstance(actual, dict) or any(
                    actual.get(field) != market[field]
                    for field in (
                        "source_type",
                        "broker_provider",
                        "broker_account_id",
                        "broker_environment",
                        "broker_symbol_id",
                    )
                ):
                    raise ValueError("Broker instrument no longer matches the stored Market source")
                if any(
                    str(actual.get(field, "")).strip().upper() != str(market[field]).strip().upper()
                    for field in ("symbol", "exchange")
                ):
                    raise ValueError("Broker instrument identity changed; create a new Market")
