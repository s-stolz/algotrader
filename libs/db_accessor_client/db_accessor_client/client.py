"""HTTP clients for database-accessor-api."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Iterable

import httpx
import pandas as pd

from .errors import DatabaseAccessorClientError
from .timeframes import normalize_timeframe_code


def _build_params(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


def _candles_to_dataframe(
    data: list[dict[str, Any]],
    *,
    include_timestamp_ms: bool = False,
) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if not df.empty and "timestamp_ms" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        if not include_timestamp_ms:
            df = df.drop(columns=["timestamp_ms"])
    return df


class _BaseClient:
    def __init__(self) -> None:
        host = os.getenv("DATABASE_ACCESSOR_HOST", "database-accessor-api")
        port = os.getenv("DATABASE_ACCESSOR_PORT", "8000")
        self.base_url = f"http://{host}:{port}".rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"


class DatabaseAccessorClient(_BaseClient):
    """Synchronous client for database-accessor-api."""

    def __init__(self, timeout: int = 30) -> None:
        super().__init__()
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self) -> DatabaseAccessorClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.client.request(method, self._url(path), **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise DatabaseAccessorClientError(
                f"database-accessor-api HTTP error: {exc.response.status_code}",
                status_code=exc.response.status_code,
                response_text=exc.response.text,
            ) from exc
        except httpx.HTTPError as exc:
            raise DatabaseAccessorClientError(
                f"database-accessor-api request failed: {exc}"
            ) from exc

    def get_markets(
        self,
        symbol: str | None = None,
        exchange: str | None = None,
    ) -> list[dict[str, Any]]:
        params = _build_params(symbol=symbol, exchange=exchange)
        return self._request("GET", "/markets", params=params)

    def get_market(
        self,
        symbol: str,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        params = _build_params(exchange=exchange)
        return self._request("GET", f"/markets/{symbol}", params=params)

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
    ) -> pd.DataFrame:
        params = _build_params(
            exchange=exchange,
            timeframe=normalize_timeframe_code(timeframe),
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
        )
        data = self._request("GET", f"/candles/{symbol}", params=params)
        return _candles_to_dataframe(data, include_timestamp_ms=include_timestamp_ms)

    def get_candles_multi(
        self,
        symbols: Iterable[str],
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
    ) -> dict[str, pd.DataFrame]:
        return {
            symbol: self.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                exchange=exchange,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
                include_timestamp_ms=include_timestamp_ms,
            )
            for symbol in symbols
        }

    def get_latest_candle(
        self, symbol: str, timeframe: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        timeframe_code = normalize_timeframe_code(timeframe)
        if timeframe_code == "M1":
            return self.get_latest_m1_candle(symbol=symbol, exchange=exchange)

        candles = self.get_candles(
            symbol=symbol,
            timeframe=timeframe_code,
            exchange=exchange,
            limit=1,
            include_timestamp_ms=True,
        )
        if candles.empty:
            return None
        return candles.iloc[0].to_dict()

    def get_latest_m1_candle(
        self, symbol: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        params = _build_params(exchange=exchange)
        try:
            return self._request("GET", f"/candles/{symbol}/latest", params=params)
        except DatabaseAccessorClientError as exc:
            if exc.status_code == 404:
                return None
            raise

    def insert_candles(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        exchange: str | None = None,
    ) -> dict[str, Any]:
        payload = {"symbol": symbol, "candles": candles}
        if exchange is not None:
            payload["exchange"] = exchange
        return self._request("POST", "/candles", json=payload)

    def close(self) -> None:
        self.client.close()


class AsyncDatabaseAccessorClient(_BaseClient):
    """Asynchronous client for database-accessor-api."""

    def __init__(self, timeout: int = 30) -> None:
        super().__init__()
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "AsyncDatabaseAccessorClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self.client.request(method, self._url(path), **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise DatabaseAccessorClientError(
                f"database-accessor-api HTTP error: {exc.response.status_code}",
                status_code=exc.response.status_code,
                response_text=exc.response.text,
            ) from exc
        except httpx.HTTPError as exc:
            raise DatabaseAccessorClientError(
                f"database-accessor-api request failed: {exc}"
            ) from exc

    async def get_markets(
        self,
        symbol: str | None = None,
        exchange: str | None = None,
    ) -> list[dict[str, Any]]:
        params = _build_params(symbol=symbol, exchange=exchange)
        return await self._request("GET", "/markets", params=params)

    async def get_market(
        self,
        symbol: str,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        params = _build_params(exchange=exchange)
        return await self._request("GET", f"/markets/{symbol}", params=params)

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
    ) -> pd.DataFrame:
        params = _build_params(
            exchange=exchange,
            timeframe=normalize_timeframe_code(timeframe),
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
        )
        data = await self._request("GET", f"/candles/{symbol}", params=params)
        return _candles_to_dataframe(data, include_timestamp_ms=include_timestamp_ms)

    async def get_candles_multi(
        self,
        symbols: Iterable[str],
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
    ) -> dict[str, pd.DataFrame]:
        symbol_list = list(symbols)
        if not symbol_list:
            return {}
        results = await asyncio.gather(
            *(
                self.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    exchange=exchange,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    limit=limit,
                    include_timestamp_ms=include_timestamp_ms,
                )
                for symbol in symbol_list
            )
        )
        return dict(zip(symbol_list, results))

    async def get_latest_candle(
        self, symbol: str, timeframe: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        timeframe_code = normalize_timeframe_code(timeframe)
        if timeframe_code == "M1":
            return await self.get_latest_m1_candle(symbol=symbol, exchange=exchange)

        candles = await self.get_candles(
            symbol=symbol,
            timeframe=timeframe_code,
            exchange=exchange,
            limit=1,
            include_timestamp_ms=True,
        )
        if candles.empty:
            return None
        return candles.iloc[0].to_dict()

    async def get_latest_m1_candle(
        self, symbol: str, exchange: str | None = None
    ) -> dict[str, Any] | None:
        params = _build_params(exchange=exchange)
        try:
            return await self._request("GET", f"/candles/{symbol}/latest", params=params)
        except DatabaseAccessorClientError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def insert_candles(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        exchange: str | None = None,
    ) -> dict[str, Any]:
        payload = {"symbol": symbol, "candles": candles}
        if exchange is not None:
            payload["exchange"] = exchange
        return await self._request("POST", "/candles", json=payload)

    async def aclose(self) -> None:
        await self.client.aclose()
