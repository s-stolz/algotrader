import asyncio
import os
from typing import Dict, Iterable

import pandas as pd
from db_accessor_client import (
    AsyncDatabaseAccessorClient,
    DatabaseAccessorClient,
    DatabaseAccessorClientError,
)
from logger import logger

log = logger(__name__)


def get_candles_sync(
    symbol_ids_mapping: Dict[str, int],
    timeframe: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> pd.DataFrame:
    """Synchronous wrapper around the async get_candles function."""
    all_dataframes = []

    for symbol, symbol_id in symbol_ids_mapping.items():
        df = _fetch_candles_sync(symbol_id, timeframe, start_ms, end_ms, limit)

        df.columns = pd.MultiIndex.from_product([df.columns, [symbol]])
        all_dataframes.append(df)

    if not all_dataframes:
        return pd.DataFrame()
    return pd.concat(all_dataframes, axis=1)


async def get_candles(
    symbol_id: int | Iterable[int],
    timeframe: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
    concurrency: int = 10,
) -> pd.DataFrame:
    """Fetch candles for one or many symbols.

    - If 'symbol_id' is an int: returns a single DataFrame.
    - If 'symbol_id' is an iterable of ints: returns a MultiIndex DataFrame

    Concurrency controls the number of parallel requests when fetching multiple symbols.
    """

    db_host = os.getenv("DATABASE_ACCESSOR_HOST", "database-accessor-api")
    db_port = os.getenv("DATABASE_ACCESSOR_PORT", "8000")
    base_url = f"http://{db_host}:{db_port}"

    # Single symbol path
    if isinstance(symbol_id, int):
        try:
            async with AsyncDatabaseAccessorClient(base_url=base_url, timeout=30) as client:
                data = await client.get_candles(
                    symbol_id=symbol_id,
                    timeframe=timeframe,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    limit=limit,
                )
            return _candles_to_dataframe(data)
        except DatabaseAccessorClientError as e:
            log.error(f"Error in get_candles for symbol {symbol_id}: {e}")
            return pd.DataFrame()

    # Multiple symbols path
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_fetch(
        client: AsyncDatabaseAccessorClient, symbol_id: int
    ) -> tuple[int, pd.DataFrame]:
        async with semaphore:
            try:
                data = await client.get_candles(
                    symbol_id=symbol_id,
                    timeframe=timeframe,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    limit=limit,
                )
                return symbol_id, _candles_to_dataframe(data)
            except DatabaseAccessorClientError as e:
                log.error(f"Error in get_candles for symbol {symbol_id}: {e}")
                return symbol_id, pd.DataFrame()

    all_dataframes = []
    async with AsyncDatabaseAccessorClient(base_url=base_url, timeout=30) as client:
        tasks = [asyncio.create_task(_bounded_fetch(client, s)) for s in symbol_id]
        for coro in asyncio.as_completed(tasks):
            fetched_symbol_id, df = await coro
            df.columns = pd.MultiIndex.from_product([df.columns, [fetched_symbol_id]])
            all_dataframes.append(df)
            log.debug(f"Fetched candles for symbol {fetched_symbol_id}:\n{df}")

    if not all_dataframes:
        return pd.DataFrame()
    return pd.concat(all_dataframes, axis=1)


def _fetch_candles_sync(
    symbol_id: int,
    timeframe: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> pd.DataFrame:
    """Synchronous HTTP fetch and DataFrame construction.
    Separated to allow running in a thread from async callers.
    """
    db_host = os.getenv("DATABASE_ACCESSOR_HOST", "database-accessor-api")
    db_port = os.getenv("DATABASE_ACCESSOR_PORT", "8000")
    base_url = f"http://{db_host}:{db_port}"
    try:
        with DatabaseAccessorClient(base_url=base_url, timeout=30) as client:
            data = client.get_candles(
                symbol_id=symbol_id,
                timeframe=timeframe,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
            )
        return _candles_to_dataframe(data)
    except DatabaseAccessorClientError as e:
        log.error(f"Error in _fetch_candles_sync for symbol {symbol_id}: {e}")
        return pd.DataFrame()


def _candles_to_dataframe(data: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if not df.empty and "timestamp_ms" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)  # type: ignore[index]
        df.set_index("timestamp", inplace=True)
    return df
