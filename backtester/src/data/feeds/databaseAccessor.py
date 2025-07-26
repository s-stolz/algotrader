import requests
import logging
import pandas as pd
from decouple import config
from typing import List

log = logging.getLogger(__name__)


class Database:
    """Database client that uses the database accessor API instead of direct database connections."""

    api_base_url = None

    @staticmethod
    def _get_api_url():
        """Get the API base URL from environment or use default."""
        if Database.api_base_url is None:
            HOST = config('DATABASE_API_HOST', default='database-accessor-api')
            PORT = config('DATABASE_API_PORT', default='8000')

            Database.api_base_url = f"http://{HOST}:{PORT}"
        return Database.api_base_url

    @staticmethod
    def _make_request(method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the database API."""
        url = f"{Database._get_api_url()}{endpoint}"
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            log.error(f"API request failed: {method} {url} - {e}")

    @staticmethod
    def get_market(symbol_id: int) -> tuple[str, str]:
        """Get market by symbol_id."""
        try:
            response = Database._make_request('GET', f'/markets/{symbol_id}')
            market = response.json()
            return (market['symbol'], market['exchange'])
        except Exception as e:
            log.error(f"Error getting symbol: {e}")
            return None

    @staticmethod
    def get_symbol_id(symbol: str, exchange: str = None) -> int:
        """Get symbol_id by symbol and exchange."""
        try:
            params = {'symbol': symbol, 'exchange': exchange}
            response = Database._make_request(
                'GET',
                '/markets',
                params=params
            )
            markets = response.json()

            return markets[0]['symbol_id'] if markets else None
        except Exception as e:
            log.error(f"Error getting symbol_id: {e}")
            return None

    @staticmethod
    def get_candles(symbol_id: int, timeframe: int, start_date: str = None, end_date: str = None, limit: int = None) -> list:
        """Get aggregated candles from the database."""
        try:
            params = {
                'timeframe': timeframe
            }
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date
            if limit:
                params['limit'] = limit

            response = Database._make_request(
                'GET',
                f'/candles/{symbol_id}',
                params=params,
            )
            candles = response.json()

            result = []
            for candle in candles:
                result.append((
                    candle['timestamp'],
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume'],
                ))

            return result

        except Exception as e:
            log.error(f"Error getting candles: {e}")
            return []
