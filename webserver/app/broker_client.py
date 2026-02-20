import logging
from typing import Dict
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class BrokerClient:
    def __init__(self, base_url: str, account_id: str):
        self.base_url = base_url.rstrip('/')
        self.account_id = account_id
        self.active_streams: Dict[str, dict] = {}
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def start_tick_stream(
        self,
        symbol: str,
        queue_size: int = 1000,
        max_stream_length: int = 10000
    ) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/tick-stream/start"
        params = {
            'queueSize': str(queue_size),
            'maxStreamLength': str(max_stream_length)
        }

        try:
            response = await self.client.get(
                f"{url}?{urlencode(params)}",
                headers={'X-Account-Id': self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            self.active_streams[f"tick:{symbol}"] = {
                'type': 'tick',
                'symbol': symbol
            }
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error starting tick stream for {symbol}: {e}")
            raise

    async def stop_tick_stream(self, symbol: str) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/tick-stream/stop"

        try:
            response = await self.client.get(
                url,
                headers={'X-Account-Id': self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            self.active_streams.pop(f"tick:{symbol}", None)
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error stopping tick stream for {symbol}: {e}")
            raise

    async def start_trendbar_stream(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/start"
        params = {
            'timeframe': timeframe,
            'onlyCompletedBars': 'true'
        }

        try:
            response = await self.client.get(
                f"{url}?{urlencode(params)}",
                headers={'X-Account-Id': self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            self.active_streams[f"trendbar:{symbol}:{timeframe}"] = {
                'type': 'trendbar',
                'symbol': symbol,
                'timeframe': timeframe
            }
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error starting trendbar stream for {symbol} {timeframe}: {e}")
            raise

    async def stop_trendbar_stream(self, symbol: str, timeframe: str) -> dict:
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/stop"
        params = {'timeframe': timeframe}

        try:
            response = await self.client.get(
                f"{url}?{urlencode(params)}",
                headers={'X-Account-Id': self.account_id}
            )
            response.raise_for_status()

            data = response.json()
            self.active_streams.pop(f"trendbar:{symbol}:{timeframe}", None)
            return data

        except httpx.HTTPError as e:
            logger.error(f"Error stopping trendbar stream for {symbol} {timeframe}: {e}")
            raise

    def get_active_streams(self) -> Dict[str, dict]:
        return self.active_streams.copy()
