"""HTTP client for database-accessor-api interactions."""
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("ingestion-service.db_client")


class DatabaseClient:
    """Client for interacting with the database-accessor-api."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize the database client.
        
        Args:
            base_url: Base URL of the database-accessor-api (e.g., http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def get_markets(self) -> List[Dict[str, Any]]:
        """Fetch all markets/symbols from the database.
        
        Returns:
            List of market dictionaries with keys: id, symbol, exchange, market_type, etc.
        """
        url = f"{self.base_url}/markets"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            markets = response.json()
            logger.info(f"Fetched {len(markets)} markets from database")
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            raise
    
    def get_latest_candle(
        self, 
        symbol_id: int, 
        timeframe: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch the most recent candle for a symbol/timeframe.
        
        Args:
            symbol_id: Database ID of the symbol
            timeframe: Timeframe in minutes (e.g., 1 for M1, 5 for M5)
            
        Returns:
            Candle dictionary or None if no candles exist
        """
        url = f"{self.base_url}/candles/{symbol_id}"
        params = {"timeframe": timeframe, "limit": 1}
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            candles = response.json()
            
            if candles and len(candles) > 0:
                return candles[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching latest candle for symbol {symbol_id}: {e}")
            return None
    
    def write_candles(
        self, 
        symbol_id: int, 
        candles: List[Dict[str, Any]]
    ) -> bool:
        """Write candles to the database in batch.
        
        Args:
            symbol_id: Database ID of the symbol
            candles: List of candle dictionaries with keys: timestamp, open, high, low, close, volume
            
        Returns:
            True if successful, False otherwise
        """
        if not candles:
            return True
            
        url = f"{self.base_url}/candles"
        payload = {
            "symbol_id": symbol_id,
            "candles": candles
        }
        
        try:
            logger.debug(f"Sending {len(candles)} candles to {url}")
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"Wrote {len(candles)} candles for symbol_id={symbol_id} - "
                f"API response: {result.get('added_candles', 0)} added"
            )
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error writing candles for symbol {symbol_id}: "
                f"{e.response.status_code} - {e.response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"Error writing candles for symbol {symbol_id}: {e}")
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
