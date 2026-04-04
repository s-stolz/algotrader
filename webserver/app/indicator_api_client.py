import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class IndicatorApiClient:
    def __init__(self, base_url: str, account_id: str):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def start_live_indicator_stream(
        self,
        *,
        symbol: str,
        timeframe: str,
        indicator_id: int,
        parameters: Optional[Dict[str, Any]] = None,
        exchange: Optional[str] = None,
    ) -> dict:
        payload = {
            "account_id": self.account_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "indicator_id": indicator_id,
            "exchange": exchange,
            "parameters": parameters or {},
        }

        url = f"{self.base_url}/indicator-streams/start"
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(
                "Error starting indicator stream for %s %s indicator=%s: %s",
                symbol,
                timeframe,
                indicator_id,
                e,
            )
            raise

    async def stop_live_indicator_stream(
        self,
        *,
        symbol: str,
        timeframe: str,
        indicator_id: int,
        parameters: Optional[Dict[str, Any]] = None,
        exchange: Optional[str] = None,
    ) -> dict:
        payload = {
            "account_id": self.account_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "indicator_id": indicator_id,
            "exchange": exchange,
            "parameters": parameters or {},
        }

        url = f"{self.base_url}/indicator-streams/stop"
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(
                "Error stopping indicator stream for %s %s indicator=%s: %s",
                symbol,
                timeframe,
                indicator_id,
                e,
            )
            raise
