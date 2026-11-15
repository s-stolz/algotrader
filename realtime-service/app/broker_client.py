import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class BrokerClient:
    def __init__(self, base_url: str, account_id: str):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def start_trendbar_stream(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/start"
        params = {
            "timeframe": timeframe,
        }

        try:
            response = await self.client.get(
                f"{url}?{urlencode(params)}", headers={"X-Account-Id": self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error starting trendbar stream for {symbol} {timeframe}: {e}")
            raise

    async def stop_trendbar_stream(self, symbol: str, timeframe: str) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/stop"
        params = {"timeframe": timeframe}

        try:
            response = await self.client.get(
                f"{url}?{urlencode(params)}", headers={"X-Account-Id": self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error stopping trendbar stream for {symbol} {timeframe}: {e}")
            raise
