import json
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from decouple import config

log = logging.getLogger(__name__)


class Database:
    """Database client that uses the database accessor API instead of direct database connections."""

    api_base_url = None

    @staticmethod
    def _get_api_url():
        """Get the API base URL from environment or use default."""
        if Database.api_base_url is None:
            HOST = config('DATABASE_ACCESSOR_HOST', default='database-accessor-api')
            PORT = config('DATABASE_ACCESSOR_PORT', default='8000')

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
            response = requests.Response()
            response.status_code = 500
            try:
                response._content = json.dumps({'error': str(e)}).encode('utf-8')
                response.headers['Content-Type'] = 'application/json'
            except Exception:
                response._content = b'{"error":"internal_error"}'
            return response

    @staticmethod
    def _to_epoch_ms(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def get_candles(
                    symbol: str,
                    timeframe: str,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    limit: Optional[int] = None,
                    exchange: Optional[str] = None,
                    ) -> list:
        """Get aggregated candles from the database."""
        try:
            params: dict[str, object] = {
                'timeframe': timeframe.upper()
            }
            if start_date:
                params['start_ms'] = Database._to_epoch_ms(start_date)
            if end_date:
                params['end_ms'] = Database._to_epoch_ms(end_date)
            if limit:
                params['limit'] = limit
            if exchange:
                params['exchange'] = exchange

            response = Database._make_request(
                'GET',
                f'/candles/{symbol}',
                params=params,
            )
            candles = response.json()

            result = []
            for candle in candles:
                result.append((
                    candle['timestamp_ms'],
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
