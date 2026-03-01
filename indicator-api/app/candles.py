import asyncio
import os
from typing import Dict, Iterable

import pandas as pd
import requests
from logger import logger

log = logger(__name__)


def get_candles_sync(
    symbol_ids_mapping: Dict[str, int],
    timeframe: int,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> pd.DataFrame:
    """Synchronous wrapper around the async get_candles function."""
    all_dataframes = []

    for symbol, symbol_id in symbol_ids_mapping.items():
        df = _fetch_candles_sync(
            symbol_id, timeframe, start_ms, end_ms, limit
        )

        df.columns = pd.MultiIndex.from_product([df.columns, [symbol]])
        all_dataframes.append(df)

    combined_df = pd.concat(all_dataframes, axis=1)
    return combined_df


async def get_candles(
    symbol_id: int | Iterable[int],
    timeframe: int,
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

    # Single symbol path
    if isinstance(symbol_id, int):
        return await asyncio.to_thread(
            _fetch_candles_sync, symbol_id, timeframe, start_ms, end_ms, limit
        )

    # Multiple symbols path
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_fetch(symbol_id: int) -> tuple[int, pd.DataFrame]:
        async with semaphore:
            df = await asyncio.to_thread(
                _fetch_candles_sync, symbol_id, timeframe, start_ms, end_ms, limit
            )
            return symbol_id, df

    tasks = [asyncio.create_task(_bounded_fetch(s)) for s in symbol_id]

    all_dataframes = []
    results = pd.DataFrame()
    for coro in asyncio.as_completed(tasks):
        symbol_id, df = await coro
        results = pd.concat([results, df])
        df.columns = pd.MultiIndex.from_product([df.columns, [symbol_id]])
        all_dataframes.append(df)
        log.debug(f"Fetched candles for symbol {symbol_id}:\n{df}")

    results = pd.concat(all_dataframes, axis=1)
    return results


def _fetch_candles_sync(
    symbol_id: int,
    timeframe: int,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> pd.DataFrame:
    """Synchronous HTTP fetch and DataFrame construction.
    Separated to allow running in a thread from async callers.
    """
    db_host = os.getenv("DATABASE_ACCESSOR_HOST", "database-accessor-api")
    db_port = os.getenv("DATABASE_ACCESSOR_PORT", "8000")
    base_url = f"http://{db_host}:{db_port}/candles/{symbol_id}"
    params = _build_params(timeframe, start_ms, end_ms, limit)
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data)
        if not df.empty and "timestamp_ms" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)  # type: ignore[index]
            df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        log.error(f"Error in _fetch_candles_sync for symbol {symbol_id}: {e}")
        return pd.DataFrame()


def _build_params(
    timeframe: int,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> dict:
    params = {"timeframe": timeframe}
    optional = {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "limit": limit,
    }
    params.update({k: v for k, v in optional.items() if v is not None})
    return params
