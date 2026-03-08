"""HTTP client for broker-service interactions."""
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.utils import normalize_timestamp_to_epoch_ms

logger = logging.getLogger("ingestion-service.broker_client")


class BrokerClient:
    """Client for interacting with the broker-service API."""

    def __init__(self, base_url: str, account_id: str, timeout: int = 30):
        """Initialize the broker client.

        Args:
            base_url: Base URL of the broker-service (e.g., http://localhost:8080)
            account_id: Broker account ID for API requests
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.timeout = timeout
        headers = {"X-Account-Id": account_id}
        self.client = httpx.Client(timeout=timeout, headers=headers)
        self.async_client = httpx.AsyncClient(timeout=timeout, headers=headers)

    def get_trendbars(
        self,
        symbol: str,
        timeframe: str = "M1",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical trendbars (candles) from the broker-service.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: Timeframe enum (e.g., "M1", "H1", "D1")
            start_time: Optional start timestamp (ISO format or epoch millis)
            end_time: Optional end timestamp (ISO format or epoch millis)
            limit: Optional maximum number of bars to return (1-1000)

        Returns:
            List of trendbar dictionaries with OHLC data
        """
        url = f"{self.base_url}/symbols/{symbol}/trendbars"

        params = {
            "timeframe": timeframe,
        }

        if start_time:
            params["fromTs"] = normalize_timestamp_to_epoch_ms(start_time)

        if end_time:
            params["toTs"] = normalize_timestamp_to_epoch_ms(end_time)

        if limit:
            params["limit"] = min(limit, 1000)  # Enforce max limit

        try:
            logger.debug(f"Fetching trendbars: {url} with params {params}")
            response = self.client.get(url, params=params)
            response.raise_for_status()
            trendbars = response.json()
            logger.info(f"Fetched {len(trendbars)} trendbars for {symbol} {timeframe}")
            return trendbars
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching trendbars: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching trendbars: {e}")
            raise

    async def stream_trendbars(
        self,
        symbol: str,
        timeframe: str = "M1",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream historical trendbars from the broker-service.

        Uses the streaming endpoint for memory-efficient processing of large
        historical data requests. Yields trendbars one at a time.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: Timeframe enum (e.g., "M1", "H1", "D1")
            start_time: Optional start timestamp (ISO format or epoch millis)
            end_time: Optional end timestamp (ISO format or epoch millis)
            limit: Optional maximum number of bars to return

        Yields:
            Trendbar dictionaries with OHLC data
        """
        url = f"{self.base_url}/symbols/{symbol}/trendbars/stream"

        params = {
            "timeframe": timeframe,
        }

        if start_time:
            params["fromTs"] = normalize_timestamp_to_epoch_ms(start_time)

        if end_time:
            params["toTs"] = normalize_timestamp_to_epoch_ms(end_time)

        if limit:
            params["limit"] = limit

        try:
            logger.debug(f"Streaming trendbars: {url} with params {params}")
            count = 0

            async with self.async_client.stream("GET", url, params=params) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        trendbar = json.loads(line)
                        count += 1
                        yield trendbar

            logger.info(f"Streamed {count} trendbars for {symbol} {timeframe}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error streaming trendbars: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error streaming trendbars: {e}")
            raise

    async def start_trendbar_stream(
        self,
        symbol: str,
        timeframe: str = "M1",
    ) -> Dict[str, Any]:
        """Start a live trendbar stream that publishes to Redis.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: Timeframe enum (e.g., "M1", "H1", "D1")

        Returns:
            Stream status dictionary
        """
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/start"
        params = {
            "timeframe": timeframe,
        }

        try:
            logger.info(f"Starting trendbar stream for {symbol} {timeframe}")
            response = await self.async_client.get(url, params=params)
            response.raise_for_status()
            status = response.json()
            logger.info(f"Started trendbar stream: {status}")
            return status
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error starting trendbar stream: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error starting trendbar stream: {e}")
            raise

    async def stop_trendbar_stream(
        self,
        symbol: str,
        timeframe: str = "M1"
    ) -> Dict[str, Any]:
        """Stop a live trendbar stream.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: Timeframe enum (e.g., "M1", "H1", "D1")

        Returns:
            Stream status dictionary
        """
        url = f"{self.base_url}/symbols/{symbol}/trendbar-stream/stop"
        params = {"timeframe": timeframe}

        try:
            logger.info(f"Stopping trendbar stream for {symbol} {timeframe}")
            response = await self.async_client.get(url, params=params)
            response.raise_for_status()
            status = response.json()
            logger.info(f"Stopped trendbar stream: {status}")
            return status
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error stopping trendbar stream: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error stopping trendbar stream: {e}")
            raise

    async def get_meta_health(self) -> Dict[str, Any]:
        """Get broker-service health information."""
        url = f"{self.base_url}/meta/health"
        try:
            response = await self.async_client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching broker health: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching broker health: {e}")
            raise

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    async def aclose(self) -> None:
        """Close the async HTTP client."""
        await self.async_client.aclose()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
