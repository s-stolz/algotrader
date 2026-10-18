"""Compatibility wrapper around the shared db_accessor_client package."""

from __future__ import annotations

import logging
from typing import Any

from db_accessor_client import DatabaseAccessorClient, DatabaseAccessorClientError

logger = logging.getLogger("ingestion-service.db_client")


class DatabaseClient:
    """Client for interacting with the database-accessor-api."""

    def __init__(self, timeout: int = 30):
        self._client = DatabaseAccessorClient(timeout=timeout)

    def get_markets(self) -> list[dict[str, Any]]:
        try:
            markets = self._client.get_markets()
            logger.info("Fetched %d markets from database", len(markets))
            return markets
        except DatabaseAccessorClientError as exc:
            logger.error("Error fetching markets: %s", exc)
            raise

    def get_latest_candle(
        self, symbol: str, timeframe: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        try:
            return self._client.get_latest_candle(
                symbol=symbol,
                timeframe=timeframe,
                exchange=exchange,
            )
        except DatabaseAccessorClientError as exc:
            logger.error("Error fetching latest candle for symbol %s: %s", symbol, exc)
            return None

    def get_latest_m1_candle(
        self, symbol: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        try:
            return self._client.get_latest_m1_candle(
                symbol=symbol,
                exchange=exchange,
            )
        except DatabaseAccessorClientError as exc:
            logger.error("Error fetching latest M1 candle for symbol %s: %s", symbol, exc)
            return None

    def write_candles(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        exchange: str | None = None,
    ) -> bool:
        if not candles:
            return True

        try:
            result = self._client.insert_candles(
                symbol=symbol,
                exchange=exchange,
                candles=candles,
            )
            logger.info(
                "Wrote %d candles for %s - API response: %s added",
                len(candles),
                symbol,
                result.get("added_candles", 0),
            )
            return True
        except DatabaseAccessorClientError as exc:
            logger.error("HTTP error writing candles for symbol %s: %s", symbol, exc)
            return False

    def close(self) -> None:
        self._client.close()
