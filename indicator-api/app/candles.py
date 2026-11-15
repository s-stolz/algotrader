import asyncio
from typing import Iterable

import pandas as pd
from algotrader_logger import get_logger
from db_accessor_client import (
    AsyncDatabaseAccessorClient,
    DatabaseAccessorClientError,
)

log = get_logger(__name__)


async def get_candles(
    symbol: str | Iterable[str],
    timeframe: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
    exchange: str | None = None,
    concurrency: int = 10,
) -> pd.DataFrame:
    """Fetch candles for one or many symbols.

    - If 'symbol' is a string: returns a single DataFrame.
    - If 'symbol' is an iterable of strings: returns a MultiIndex DataFrame

    Concurrency controls the number of parallel requests when fetching multiple symbols.
    """

    # Single symbol path
    if isinstance(symbol, str):
        try:
            async with AsyncDatabaseAccessorClient() as client:
                data = await client.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    exchange=exchange,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    limit=limit,
                )
            return data
        except DatabaseAccessorClientError as e:
            log.error(f"Error in get_candles for symbol {symbol}: {e}")
            return pd.DataFrame()

    # Multiple symbols path
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_fetch(
        client: AsyncDatabaseAccessorClient, symbol: str
    ) -> tuple[str, pd.DataFrame]:
        async with semaphore:
            try:
                data = await client.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    exchange=exchange,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    limit=limit,
                )
                return symbol, data
            except DatabaseAccessorClientError as e:
                log.error(f"Error in get_candles for symbol {symbol}: {e}")
                return symbol, pd.DataFrame()

    all_dataframes = []
    async with AsyncDatabaseAccessorClient() as client:
        tasks = [asyncio.create_task(_bounded_fetch(client, s)) for s in symbol]
        for coro in asyncio.as_completed(tasks):
            fetched_symbol, df = await coro
            df.columns = pd.MultiIndex.from_product([df.columns, [fetched_symbol]])
            all_dataframes.append(df)
            log.debug(f"Fetched candles for symbol {fetched_symbol}:\n{df}")

    if not all_dataframes:
        return pd.DataFrame()
    return pd.concat(all_dataframes, axis=1)
