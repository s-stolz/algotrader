"""Host-side smoke check for the durable asynchronous backtester workflow."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from time import monotonic
from time import sleep as default_sleep
from typing import Any, Callable, Mapping, Protocol, cast
from uuid import uuid4

import httpx

FIXTURE_SYMBOL = "BTESMOKE"
FIXTURE_EXCHANGE = "SMOKE"
FIXTURE_START_MS = 1_700_000_000_000
_TERMINAL_STATUSES = {"succeeded", "failed"}


class SmokeCheckError(RuntimeError):
    """Raised when the deployed asynchronous workflow violates its contract."""


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class HttpClient(Protocol):
    def get(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> HttpResponse: ...

    def post(self, path: str, *, json: Mapping[str, Any]) -> HttpResponse: ...

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> HttpResponse: ...

    def close(self) -> None: ...


class _HttpxClient:
    def __init__(self, *, base_url: str, timeout: float) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return cast(HttpResponse, self._client.get(path, params=params))

    def post(self, path: str, *, json: Mapping[str, Any]) -> HttpResponse:
        return cast(HttpResponse, self._client.post(path, json=json))

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return cast(HttpResponse, self._client.delete(path, params=params))

    def close(self) -> None:
        self._client.close()


@dataclass(frozen=True)
class SmokeReport:
    success_run_id: str
    success_statuses: tuple[str, ...]
    success_fill_count: int
    success_trade_count: int
    failure_run_id: str
    failure_status: str
    failure_fill_count: int
    failure_trade_count: int


@dataclass
class _CleanupState:
    fixture_created: bool = False
    terminal_run_ids: list[str] = field(default_factory=list)


def run_smoke(
    *,
    backtester_url: str | None = None,
    storage_url: str | None = None,
    backtester_client: HttpClient | None = None,
    storage_client: HttpClient | None = None,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = default_sleep,
    failure_symbol: str | None = None,
) -> SmokeReport:
    _validate_options(timeout_seconds, poll_interval_seconds)
    owned_backtester = backtester_client is None
    owned_storage = storage_client is None
    api = backtester_client or _HttpxClient(
        base_url=backtester_url or _default_backtester_url(),
        timeout=timeout_seconds,
    )
    storage = storage_client or _HttpxClient(
        base_url=storage_url or _default_storage_url(),
        timeout=timeout_seconds,
    )
    cleanup = _CleanupState()

    try:
        return _exercise_paths(
            api=api,
            storage=storage,
            cleanup=cleanup,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
            failure_symbol=failure_symbol or f"SMK{uuid4().hex[:7].upper()}",
        )
    finally:
        _cleanup_resources(api, storage, cleanup)
        _close_owned_clients(api, storage, owned_backtester, owned_storage)


def _exercise_paths(
    *,
    api: HttpClient,
    storage: HttpClient,
    cleanup: _CleanupState,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
    failure_symbol: str,
) -> SmokeReport:
    _seed_fixture(storage, cleanup)
    success_run_id, success_statuses, success_fill_count, success_trade_count = (
        _exercise_success_path(
            api,
            cleanup=cleanup,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
    )
    failure_run_id, failure_status, failure_fill_count, failure_trade_count = (
        _exercise_failure_path(
            api,
            cleanup=cleanup,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
            failure_symbol=failure_symbol,
        )
    )
    return SmokeReport(
        success_run_id=success_run_id,
        success_statuses=success_statuses,
        success_fill_count=success_fill_count,
        success_trade_count=success_trade_count,
        failure_run_id=failure_run_id,
        failure_status=failure_status,
        failure_fill_count=failure_fill_count,
        failure_trade_count=failure_trade_count,
    )


def _exercise_success_path(
    api: HttpClient,
    *,
    cleanup: _CleanupState,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[str, tuple[str, ...], int, int]:
    run_id, initial_status = _submit(api, _success_request())
    run, statuses = _wait_for_terminal(
        api,
        run_id=run_id,
        initial_status=initial_status,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    cleanup.terminal_run_ids.append(run_id)
    if run["status"] != "succeeded":
        raise SmokeCheckError(f"Fixture-backed run failed: {run}")
    if not isinstance(run.get("metrics"), Mapping):
        raise SmokeCheckError("Succeeded run did not expose metrics")
    if not isinstance(run.get("diagnostics"), Mapping):
        raise SmokeCheckError("Succeeded run did not expose diagnostics")

    fills = _get_collection(api, f"/backtests/{run_id}/fills")
    trades = _get_collection(api, f"/backtests/{run_id}/trades")
    if not fills or not trades:
        raise SmokeCheckError("Fixture-backed run did not persist fills and trades")
    return run_id, statuses, len(fills), len(trades)


def _exercise_failure_path(
    api: HttpClient,
    *,
    cleanup: _CleanupState,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
    failure_symbol: str,
) -> tuple[str, str, int, int]:
    run_id, initial_status = _submit(api, _failure_request(failure_symbol))
    run, _ = _wait_for_terminal(
        api,
        run_id=run_id,
        initial_status=initial_status,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    cleanup.terminal_run_ids.append(run_id)
    if run["status"] != "failed":
        raise SmokeCheckError(f"Missing-market run did not fail: {run}")
    if "metrics" in run or "diagnostics" in run:
        raise SmokeCheckError("Failed run exposed partial result artifacts")

    fills = _get_collection(api, f"/backtests/{run_id}/fills")
    trades = _get_collection(api, f"/backtests/{run_id}/trades")
    if fills or trades:
        raise SmokeCheckError("Failed run persisted partial fills or trades")
    return run_id, str(run["status"]), len(fills), len(trades)


def _seed_fixture(client: HttpClient, cleanup: _CleanupState) -> None:
    response = client.get(
        "/markets",
        params={"symbol": FIXTURE_SYMBOL, "exchange": FIXTURE_EXCHANGE},
    )
    response.raise_for_status()
    markets = response.json()
    if not isinstance(markets, list):
        raise SmokeCheckError("Market lookup returned an invalid response")

    created = not markets
    if created:
        response = client.post(
            "/markets",
            json={
                "symbol": FIXTURE_SYMBOL,
                "exchange": FIXTURE_EXCHANGE,
                "market_type": "fixture",
                "min_move": 0.01,
                "timezone": "UTC",
            },
        )
        response.raise_for_status()
        cleanup.fixture_created = True

    response = client.post(
        "/candles",
        json={
            "symbol": FIXTURE_SYMBOL,
            "exchange": FIXTURE_EXCHANGE,
            "candles": _fixture_candles(),
        },
    )
    response.raise_for_status()


def _validate_options(timeout_seconds: float, poll_interval_seconds: float) -> None:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds must be non-negative")


def _cleanup_resources(
    api: HttpClient,
    storage: HttpClient,
    cleanup: _CleanupState,
) -> None:
    for run_id in cleanup.terminal_run_ids:
        _delete_if_possible(api, f"/backtests/{run_id}")
    if cleanup.fixture_created:
        _delete_if_possible(
            storage,
            f"/markets/{FIXTURE_SYMBOL}",
            params={"exchange": FIXTURE_EXCHANGE},
        )


def _close_owned_clients(
    api: HttpClient,
    storage: HttpClient,
    owned_backtester: bool,
    owned_storage: bool,
) -> None:
    if owned_backtester:
        api.close()
    if owned_storage:
        storage.close()


def _submit(client: HttpClient, payload: dict[str, Any]) -> tuple[str, str]:
    response = client.post("/backtests", json=payload)
    if response.status_code != 202:
        raise SmokeCheckError(f"Submission returned HTTP {response.status_code}")
    body = _require_mapping(response.json(), "submission")
    run_id = str(body.get("run_id", "")).strip()
    status = str(body.get("status", "")).strip()
    if not run_id or status != "queued":
        raise SmokeCheckError(f"Submission returned an invalid body: {body}")
    if response.headers.get("location") != f"/backtests/{run_id}":
        raise SmokeCheckError("Submission returned an invalid Location header")
    return run_id, status


def _wait_for_terminal(
    client: HttpClient,
    *,
    run_id: str,
    initial_status: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    deadline = monotonic() + timeout_seconds
    statuses = [initial_status]
    while monotonic() < deadline:
        response = client.get(f"/backtests/{run_id}")
        response.raise_for_status()
        run = dict(_require_mapping(response.json(), "run status"))
        status = str(run.get("status", ""))
        if not statuses or statuses[-1] != status:
            statuses.append(status)
        if status in _TERMINAL_STATUSES:
            return run, tuple(statuses)
        sleep(poll_interval_seconds)
    raise SmokeCheckError(f"Backtest run did not reach a terminal state: {run_id}")


def _get_collection(client: HttpClient, path: str) -> list[object]:
    response = client.get(path)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise SmokeCheckError(f"{path} returned an invalid collection")
    return payload


def _delete_if_possible(
    client: HttpClient,
    path: str,
    *,
    params: Mapping[str, str] | None = None,
) -> None:
    try:
        response = client.delete(path, params=params)
        response.raise_for_status()
    except Exception:
        return


def _success_request() -> dict[str, Any]:
    return {
        "symbols": [FIXTURE_SYMBOL],
        "exchange": FIXTURE_EXCHANGE,
        "timeframe": "M1",
        "start_ms": FIXTURE_START_MS,
        "end_ms": FIXTURE_START_MS + (9 * 60_000),
        "engine": "vectorized",
        "data_granularity": "bar",
        "initial_capital": 10_000.0,
        "strategy": {
            "strategy_id": "sma_crossover",
            "parameters": {
                "fast_window": 2,
                "slow_window": 3,
                "quantity": 1.0,
            },
        },
        "execution": {},
        "persist_result": False,
        "run_metadata": {"label": "compose-smoke-success"},
    }


def _failure_request(symbol: str) -> dict[str, Any]:
    request = _success_request()
    request["symbols"] = [symbol]
    request["exchange"] = "SMOKE-MISSING"
    request["run_metadata"] = {"label": "compose-smoke-failure"}
    return request


def _fixture_candles() -> list[dict[str, float | int]]:
    closes = [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
    first_timestamp_ms = FIXTURE_START_MS - (3 * 60_000)
    return [
        {
            "timestamp_ms": first_timestamp_ms + (index * 60_000),
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000.0,
        }
        for index, close in enumerate(closes)
    ]


def _require_mapping(payload: object, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise SmokeCheckError(f"{label} returned an invalid response")
    return payload


def _default_backtester_url() -> str:
    host = os.getenv("PUBLIC_HOST", "localhost")
    port = os.getenv("BACKTESTER_API_PUBLISHED_PORT", "8020")
    return f"http://{host}:{port}"


def _default_storage_url() -> str:
    host = os.getenv("PUBLIC_HOST", "localhost")
    port = os.getenv("DATABASE_ACCESSOR_PUBLISHED_PORT", "8000")
    return f"http://{host}:{port}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exercise the deployed asynchronous backtester success and failure paths",
    )
    parser.add_argument("--backtester-url", default=_default_backtester_url())
    parser.add_argument("--storage-url", default=_default_storage_url())
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_smoke(
        backtester_url=args.backtester_url,
        storage_url=args.storage_url,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
