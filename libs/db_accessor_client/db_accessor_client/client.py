"""HTTP clients for database-accessor-api."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import DatabaseAccessorClientError


def _build_params(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


class _BaseClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"


class DatabaseAccessorClient(_BaseClient):
    """Synchronous client for database-accessor-api."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        super().__init__(base_url)
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "DatabaseAccessorClient":
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

    def get_market(self, symbol_id: int) -> dict[str, Any]:
        return self._request("GET", f"/markets/{symbol_id}")

    def get_candles(
        self,
        symbol_id: int,
        timeframe: int,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params = _build_params(
            timeframe=timeframe,
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
        )
        return self._request("GET", f"/candles/{symbol_id}", params=params)

    def get_latest_candle(self, symbol_id: int, timeframe: int) -> dict[str, Any] | None:
        candles = self.get_candles(symbol_id=symbol_id, timeframe=timeframe, limit=1)
        return candles[0] if candles else None

    def insert_candles(self, symbol_id: int, candles: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"symbol_id": symbol_id, "candles": candles}
        return self._request("POST", "/candles", json=payload)

    def close(self) -> None:
        self.client.close()


class AsyncDatabaseAccessorClient(_BaseClient):
    """Asynchronous client for database-accessor-api."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        super().__init__(base_url)
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

    async def get_market(self, symbol_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/markets/{symbol_id}")

    async def get_candles(
        self,
        symbol_id: int,
        timeframe: int,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params = _build_params(
            timeframe=timeframe,
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
        )
        return await self._request("GET", f"/candles/{symbol_id}", params=params)

    async def get_latest_candle(self, symbol_id: int, timeframe: int) -> dict[str, Any] | None:
        candles = await self.get_candles(symbol_id=symbol_id, timeframe=timeframe, limit=1)
        return candles[0] if candles else None

    async def insert_candles(self, symbol_id: int, candles: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"symbol_id": symbol_id, "candles": candles}
        return await self._request("POST", "/candles", json=payload)

    async def aclose(self) -> None:
        await self.client.aclose()
