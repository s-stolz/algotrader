"""HTTP clients for database-accessor-api."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Iterable

import httpx
import pandas as pd

from .candle_stream import parse_candle_frame
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
        df = df.set_index("timestamp")
        if not include_timestamp_ms:
            df = df.drop(columns=["timestamp_ms"])
    return df


def _mutation_updated(response: Any) -> bool:
    if not isinstance(response, dict) or not isinstance(response.get("updated"), bool):
        raise DatabaseAccessorClientError(
            "database-accessor-api returned an invalid mutation response"
        )
    return response["updated"]


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
            if response.status_code == 204:
                return None
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

    def get_market_by_id(self, market_id: int) -> dict[str, Any]:
        return self._request("GET", f"/markets/id/{market_id}")

    def get_market_coverage(self, market_id: int) -> dict[str, Any]:
        return self._request("GET", f"/markets/id/{market_id}/coverage")

    def create_history_download_job(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/history-download-jobs", json=data)

    def list_history_download_jobs(
        self, market_id: int | None = None, active_only: bool = False, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/history-download-jobs",
            params=_build_params(
                market_id=market_id,
                active_only=active_only,
                limit=limit,
            ),
        )

    def get_history_download_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/history-download-jobs/{job_id}")

    def claim_history_download_job(
        self, job_id: str, owner_token: str, lease_seconds: int = 120
    ) -> dict[str, Any] | None:
        return self._request(
            "POST",
            f"/history-download-jobs/{job_id}/claim",
            json=dict(
                owner_token=owner_token,
                lease_seconds=lease_seconds,
            ),
        )

    def heartbeat_history_download_job(
        self, job_id: str, owner_token: str, revision: int, lease_seconds: int = 120
    ) -> dict[str, Any] | None:
        return self._request(
            "POST",
            f"/history-download-jobs/{job_id}/heartbeat",
            json=dict(
                owner_token=owner_token,
                revision=revision,
                lease_seconds=lease_seconds,
            ),
        )

    def commit_history_download_page(
        self, job_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        return self._request("POST", f"/history-download-jobs/{job_id}/pages", json=data)

    def transition_history_download_job(
        self, job_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        return self._request("POST", f"/history-download-jobs/{job_id}/transition", json=data)

    def cancel_history_download_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/history-download-jobs/{job_id}/cancel")

    def retry_history_download_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/history-download-jobs/{job_id}/retry")

    def stream_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
        exchange: str | None = None,
        market_id: int | None = None,
    ):
        params = _build_params(
            timeframe=normalize_timeframe_code(timeframe),
            start_ms=start_ms,
            end_ms=end_ms,
            exchange=exchange,
            market_id=market_id,
        )
        try:
            with self.client.stream(
                "GET",
                self._url(f"/candles/{symbol}/stream"),
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                response.raise_for_status()
                complete = False
                for line in response.iter_lines():
                    if not line:
                        continue
                    if complete:
                        raise DatabaseAccessorClientError("Data after Candle stream completion")
                    candles = parse_candle_frame(line)
                    if candles is None:
                        complete = True
                    else:
                        yield candles
                if not complete:
                    raise DatabaseAccessorClientError("Incomplete Candle stream")
        except httpx.HTTPError as exc:
            raise DatabaseAccessorClientError("Candle stream request failed") from exc

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
        market_id: int | None = None,
    ) -> pd.DataFrame:
        params = _build_params(
            market_id=market_id,
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

    def create_backtest(self, backtest: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/backtests", json=backtest)

    def rename_backtest(self, backtest_id: str, name: str | None) -> dict[str, Any]:
        return self._request("PATCH", f"/backtests/{backtest_id}/name", json={"name": name})

    def list_backtests(self) -> list[dict[str, Any]]:
        return self._request("GET", "/backtests")

    def get_backtest(self, backtest_id: str) -> dict[str, Any]:
        return self._request("GET", f"/backtests/{backtest_id}")

    def list_backtest_members(
        self, backtest_id: str, *, include_diagnostics: bool = True
    ) -> list[dict[str, Any]]:
        if include_diagnostics:
            return self._request("GET", f"/backtests/{backtest_id}/members")
        return self._request(
            "GET", f"/backtests/{backtest_id}/members", params={"include_diagnostics": False}
        )

    def list_backtest_events(self, backtest_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/backtests/{backtest_id}/events")

    def control_backtest(
        self, backtest_id: str, command: str, command_id: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/backtests/{backtest_id}/{command}",
            json={"command_id": command_id, "policy": policy},
        )

    def get_backtest_run(self, run_id: str, *, include_diagnostics: bool = True) -> dict[str, Any]:
        if include_diagnostics:
            return self._request("GET", f"/backtest-runs/{run_id}")
        return self._request(
            "GET", f"/backtest-runs/{run_id}", params={"include_diagnostics": False}
        )

    def get_backtest_fills(self, run_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/backtest-runs/{run_id}/fills")

    def get_backtest_execution_log(
        self,
        run_id: str,
        *,
        page: int = 1,
        page_size: int = 10,
        include_unexecuted: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/backtest-runs/{run_id}/execution-log",
            params={
                "page": page,
                "page_size": page_size,
                "include_unexecuted": include_unexecuted,
            },
        )

    def get_backtest_trades(self, run_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/backtest-runs/{run_id}/trades")

    def list_backtest_runs(
        self,
        *,
        status: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        engine: str | None = None,
        submitted_from: str | None = None,
        submitted_to: str | None = None,
        backtest_id: str | None = None,
        include_diagnostics: bool = True,
    ) -> list[dict[str, Any]]:
        params = _build_params(
            status=status,
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            engine=engine,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            backtest_id=backtest_id,
        )
        if not include_diagnostics:
            params["include_diagnostics"] = False
        return self._request("GET", "/backtest-runs", params=params)

    def get_backtest_execution_slot(self) -> dict[str, Any]:
        return self._request("GET", "/backtest-execution/slot")

    def get_backtest_queue_state(self) -> dict[str, Any]:
        return self._request("GET", "/backtest-execution/queue-state")

    def record_backtest_worker_heartbeat(self, heartbeat: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/backtest-execution/heartbeat", json=heartbeat)

    def claim_backtest_execution(self, claim: dict[str, Any]) -> bool:
        return _mutation_updated(self._request("POST", "/backtest-execution/claim", json=claim))

    def settle_backtest_execution(self, settlement: dict[str, Any]) -> bool:
        return _mutation_updated(
            self._request("POST", "/backtest-execution/settle", json=settlement)
        )

    def cancel_backtest_run(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/backtest-runs/{run_id}/cancel")

    def reconcile_backtest_execution(self, reconciliation: dict[str, Any]) -> int | None:
        response = self._request("POST", "/backtest-execution/reconcile", json=reconciliation)
        return response["reconciled"]

    def record_backtest_execution_fault(self, fault: dict[str, Any]) -> bool:
        return _mutation_updated(self._request("POST", "/backtest-execution/fault", json=fault))

    def delete_backtest(self, backtest_id: str) -> None:
        self._request("DELETE", f"/backtests/{backtest_id}")

    def write_historical_candles(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        start_ms: int,
        end_ms: int,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "symbol": symbol,
            "candles": candles,
            "start_ms": start_ms,
            "end_ms": end_ms,
        }
        if exchange is not None:
            payload["exchange"] = exchange
        return self._request("POST", "/candles/historical", json=payload)

    def get_pending_recovery(self, symbol_id: int, account_id: str) -> dict[str, Any] | None:
        result = self._request("GET", f"/recoveries/{symbol_id}", params={"account_id": account_id})
        return result["pending"]

    def begin_recovery(
        self, symbol_id: int, account_id: str, start_ms: int, target_ms: int, trigger: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/recoveries/begin",
            json={
                "symbol_id": symbol_id,
                "account_id": account_id,
                "start_ms": start_ms,
                "target_ms": target_ms,
                "trigger": trigger,
            },
        )

    def advance_recovery(self, pending: dict[str, Any], next_ms: int) -> bool:
        result = self._request(
            "POST",
            "/recoveries/advance",
            json={
                "symbol_id": pending["symbol_id"],
                "account_id": pending["account_id"],
                "recovery_id": pending["recovery_id"],
                "revision": pending["revision"],
                "expected_start_ms": pending["next_ms"],
                "next_ms": next_ms,
            },
        )
        return result["updated"]

    def get_live_write_guard(self, symbol_id: int, account_id: str) -> dict[str, Any] | None:
        result = self._request(
            "GET", f"/recoveries/live-writes/{symbol_id}", params={"account_id": account_id}
        )
        return result["guard"]

    def begin_live_write(self, symbol_id: int, account_id: str, boundary_ms: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/recoveries/live-writes/begin",
            json={"symbol_id": symbol_id, "account_id": account_id, "boundary_ms": boundary_ms},
        )

    def finish_live_write(self, guard: dict[str, Any]) -> bool:
        result = self._request(
            "POST",
            "/recoveries/live-writes/finish",
            json={key: guard[key] for key in ("symbol_id", "account_id", "write_id")},
        )
        return result["updated"]

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
            if response.status_code == 204:
                return None
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

    async def get_market_by_id(self, market_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/markets/id/{market_id}")

    async def get_market_coverage(self, market_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/markets/id/{market_id}/coverage")

    async def create_history_download_job(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/history-download-jobs", json=data)

    async def list_history_download_jobs(
        self, market_id: int | None = None, active_only: bool = False, limit: int = 50
    ) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/history-download-jobs",
            params=_build_params(
                market_id=market_id,
                active_only=active_only,
                limit=limit,
            ),
        )

    async def get_history_download_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/history-download-jobs/{job_id}")

    async def claim_history_download_job(
        self, job_id: str, owner_token: str, lease_seconds: int = 120
    ) -> dict[str, Any] | None:
        return await self._request(
            "POST",
            f"/history-download-jobs/{job_id}/claim",
            json=dict(
                owner_token=owner_token,
                lease_seconds=lease_seconds,
            ),
        )

    async def heartbeat_history_download_job(
        self, job_id: str, owner_token: str, revision: int, lease_seconds: int = 120
    ) -> dict[str, Any] | None:
        return await self._request(
            "POST",
            f"/history-download-jobs/{job_id}/heartbeat",
            json=dict(
                owner_token=owner_token,
                revision=revision,
                lease_seconds=lease_seconds,
            ),
        )

    async def commit_history_download_page(
        self, job_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._request("POST", f"/history-download-jobs/{job_id}/pages", json=data)

    async def transition_history_download_job(
        self, job_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._request("POST", f"/history-download-jobs/{job_id}/transition", json=data)

    async def cancel_history_download_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/history-download-jobs/{job_id}/cancel")

    async def retry_history_download_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/history-download-jobs/{job_id}/retry")

    async def stream_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
        exchange: str | None = None,
        market_id: int | None = None,
    ):
        params = _build_params(
            timeframe=normalize_timeframe_code(timeframe),
            start_ms=start_ms,
            end_ms=end_ms,
            exchange=exchange,
            market_id=market_id,
        )
        try:
            async with self.client.stream(
                "GET",
                self._url(f"/candles/{symbol}/stream"),
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                response.raise_for_status()
                complete = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if complete:
                        raise DatabaseAccessorClientError("Data after Candle stream completion")
                    candles = parse_candle_frame(line)
                    if candles is None:
                        complete = True
                    else:
                        yield candles
                if not complete:
                    raise DatabaseAccessorClientError("Incomplete Candle stream")
        except httpx.HTTPError as exc:
            raise DatabaseAccessorClientError("Candle stream request failed") from exc

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
        market_id: int | None = None,
    ) -> pd.DataFrame:
        params = _build_params(
            market_id=market_id,
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

    async def create_backtest(self, backtest: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/backtests", json=backtest)

    async def rename_backtest(self, backtest_id: str, name: str | None) -> dict[str, Any]:
        return await self._request("PATCH", f"/backtests/{backtest_id}/name", json={"name": name})

    async def list_backtests(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/backtests")

    async def get_backtest(self, backtest_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/backtests/{backtest_id}")

    async def list_backtest_members(
        self, backtest_id: str, *, include_diagnostics: bool = True
    ) -> list[dict[str, Any]]:
        if include_diagnostics:
            return await self._request("GET", f"/backtests/{backtest_id}/members")
        return await self._request(
            "GET", f"/backtests/{backtest_id}/members", params={"include_diagnostics": False}
        )

    async def list_backtest_events(self, backtest_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/backtests/{backtest_id}/events")

    async def control_backtest(
        self, backtest_id: str, command: str, command_id: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/backtests/{backtest_id}/{command}",
            json={"command_id": command_id, "policy": policy},
        )

    async def get_backtest_run(
        self, run_id: str, *, include_diagnostics: bool = True
    ) -> dict[str, Any]:
        if include_diagnostics:
            return await self._request("GET", f"/backtest-runs/{run_id}")
        return await self._request(
            "GET", f"/backtest-runs/{run_id}", params={"include_diagnostics": False}
        )

    async def get_backtest_fills(self, run_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/backtest-runs/{run_id}/fills")

    async def get_backtest_execution_log(
        self,
        run_id: str,
        *,
        page: int = 1,
        page_size: int = 10,
        include_unexecuted: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/backtest-runs/{run_id}/execution-log",
            params={
                "page": page,
                "page_size": page_size,
                "include_unexecuted": include_unexecuted,
            },
        )

    async def get_backtest_trades(self, run_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/backtest-runs/{run_id}/trades")

    async def list_backtest_runs(
        self,
        *,
        status: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        engine: str | None = None,
        submitted_from: str | None = None,
        submitted_to: str | None = None,
        backtest_id: str | None = None,
        include_diagnostics: bool = True,
    ) -> list[dict[str, Any]]:
        params = _build_params(
            status=status,
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            engine=engine,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            backtest_id=backtest_id,
        )
        if not include_diagnostics:
            params["include_diagnostics"] = False
        return await self._request("GET", "/backtest-runs", params=params)

    async def get_backtest_execution_slot(self) -> dict[str, Any]:
        return await self._request("GET", "/backtest-execution/slot")

    async def get_backtest_queue_state(self) -> dict[str, Any]:
        return await self._request("GET", "/backtest-execution/queue-state")

    async def record_backtest_worker_heartbeat(self, heartbeat: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/backtest-execution/heartbeat", json=heartbeat)

    async def claim_backtest_execution(self, claim: dict[str, Any]) -> bool:
        return _mutation_updated(
            await self._request("POST", "/backtest-execution/claim", json=claim)
        )

    async def settle_backtest_execution(self, settlement: dict[str, Any]) -> bool:
        return _mutation_updated(
            await self._request("POST", "/backtest-execution/settle", json=settlement)
        )

    async def cancel_backtest_run(self, run_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/backtest-runs/{run_id}/cancel")

    async def reconcile_backtest_execution(self, reconciliation: dict[str, Any]) -> int | None:
        response = await self._request("POST", "/backtest-execution/reconcile", json=reconciliation)
        return response["reconciled"]

    async def record_backtest_execution_fault(self, fault: dict[str, Any]) -> bool:
        return _mutation_updated(
            await self._request("POST", "/backtest-execution/fault", json=fault)
        )

    async def delete_backtest(self, backtest_id: str) -> None:
        await self._request("DELETE", f"/backtests/{backtest_id}")

    async def write_historical_candles(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        start_ms: int,
        end_ms: int,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "symbol": symbol,
            "candles": candles,
            "start_ms": start_ms,
            "end_ms": end_ms,
        }
        if exchange is not None:
            payload["exchange"] = exchange
        return await self._request("POST", "/candles/historical", json=payload)

    async def get_pending_recovery(self, symbol_id: int, account_id: str) -> dict[str, Any] | None:
        result = await self._request(
            "GET", f"/recoveries/{symbol_id}", params={"account_id": account_id}
        )
        return result["pending"]

    async def begin_recovery(
        self, symbol_id: int, account_id: str, start_ms: int, target_ms: int, trigger: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/recoveries/begin",
            json={
                "symbol_id": symbol_id,
                "account_id": account_id,
                "start_ms": start_ms,
                "target_ms": target_ms,
                "trigger": trigger,
            },
        )

    async def advance_recovery(self, pending: dict[str, Any], next_ms: int) -> bool:
        result = await self._request(
            "POST",
            "/recoveries/advance",
            json={
                "symbol_id": pending["symbol_id"],
                "account_id": pending["account_id"],
                "recovery_id": pending["recovery_id"],
                "revision": pending["revision"],
                "expected_start_ms": pending["next_ms"],
                "next_ms": next_ms,
            },
        )
        return result["updated"]

    async def get_live_write_guard(self, symbol_id: int, account_id: str) -> dict[str, Any] | None:
        result = await self._request(
            "GET", f"/recoveries/live-writes/{symbol_id}", params={"account_id": account_id}
        )
        return result["guard"]

    async def begin_live_write(
        self, symbol_id: int, account_id: str, boundary_ms: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/recoveries/live-writes/begin",
            json={"symbol_id": symbol_id, "account_id": account_id, "boundary_ms": boundary_ms},
        )

    async def finish_live_write(self, guard: dict[str, Any]) -> bool:
        result = await self._request(
            "POST",
            "/recoveries/live-writes/finish",
            json={key: guard[key] for key in ("symbol_id", "account_id", "write_id")},
        )
        return result["updated"]

    async def aclose(self) -> None:
        await self.client.aclose()
