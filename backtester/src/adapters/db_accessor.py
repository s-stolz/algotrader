"""Database accessor adapter for historical candle fetches."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

REQUIRED_CANDLE_COLUMNS = (
    "timestamp_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class CandleSourceClient(Protocol):
    """Protocol for the subset of db accessor client behavior used by the backtester."""

    def stream_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
        exchange: str | None = None,
        market_id: int | None = None,
    ) -> Iterator[list[dict[str, Any]]]: ...

    def get_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        exchange: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
        include_timestamp_ms: bool = False,
        market_id: int | None = None,
    ) -> pd.DataFrame: ...


class HistoricalBarDataAdapter(Protocol):
    """Protocol for historical bar providers used by app/data orchestration."""

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int | None,
        end_ms: int | None,
        exchange: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame: ...


class DatabaseAccessorHistoricalDataAdapter:
    """Historical candle adapter backed by ``db_accessor_client``."""

    def __init__(self, client: CandleSourceClient | None = None) -> None:
        self._client = client
        self._market_identity: tuple[str, str | None, int] | None = None

    @classmethod
    def for_request(cls, request):
        adapter = cls()
        if request.instrument is not None:
            adapter._market_identity = (
                request.symbols[0],
                request.exchange,
                request.instrument.symbol_id,
            )
        return adapter

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int | None,
        end_ms: int | None,
        exchange: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Fetch bars from the shared database accessor service and map to canonical columns."""

        candles = self._request_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_ms=start_ms,
            end_ms=end_ms,
            exchange=exchange,
            limit=limit,
        )
        return _map_to_canonical_bar_frame(candles=candles, symbol=symbol)

    def _request_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ms: int | None,
        end_ms: int | None,
        exchange: str | None,
        limit: int | None,
    ) -> pd.DataFrame:
        kwargs = {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "limit": limit,
            "include_timestamp_ms": True,
        }

        if self._market_identity is not None and (symbol, exchange) == self._market_identity[:2]:
            kwargs["market_id"] = self._market_identity[2]
        if self._client is not None:
            return _fetch_candle_frame(self._client, kwargs)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return _fetch_candle_frame(client, kwargs)


def _fetch_candle_frame(client: CandleSourceClient, kwargs: dict[str, Any]) -> pd.DataFrame:
    if kwargs["start_ms"] is None or kwargs["end_ms"] is None or kwargs["limit"] is not None:
        return client.get_candles(**kwargs)

    stream_kwargs = {
        key: value for key, value in kwargs.items() if key not in ("limit", "include_timestamp_ms")
    }
    # Exhaust the stream inside the client context, including its completion check.
    # Concatenate once to avoid repeatedly copying the accumulated history.
    frames = [pd.DataFrame(batch) for batch in client.stream_candles(**stream_kwargs) if batch]
    if not frames:
        return pd.DataFrame(columns=pd.Index(REQUIRED_CANDLE_COLUMNS))
    return pd.concat(frames, ignore_index=True)


def _import_database_accessor_client() -> type[Any]:
    try:
        from db_accessor_client import DatabaseAccessorClient
    except ModuleNotFoundError:
        _append_monorepo_lib_path("db_accessor_client")
        try:
            from db_accessor_client import DatabaseAccessorClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "db_accessor_client is required for historical backtest data fetches"
            ) from exc
    return DatabaseAccessorClient


def _map_to_canonical_bar_frame(*, candles: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if candles.empty:
        return pd.DataFrame(
            columns=pd.Index(["timestamp_ms", "symbol", "open", "high", "low", "close", "volume"])
        )

    mapped = candles.copy()
    if "timestamp_ms" not in mapped.columns:
        if isinstance(mapped.index, pd.DatetimeIndex):
            mapped["timestamp_ms"] = mapped.index.as_unit("ms").asi8
        else:
            raise ValueError(
                "Candles payload does not include timestamp_ms and index is not DatetimeIndex"
            )

    missing = [column for column in REQUIRED_CANDLE_COLUMNS if column not in mapped.columns]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Candles payload is missing required columns: {missing_text}")

    mapped = mapped.loc[:, list(REQUIRED_CANDLE_COLUMNS)].copy()
    mapped.insert(1, "symbol", symbol)
    return mapped


def _append_monorepo_lib_path(lib_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    lib_path = repo_root / "libs" / lib_name
    as_text = str(lib_path)
    if lib_path.exists() and as_text not in sys.path:
        sys.path.append(as_text)
