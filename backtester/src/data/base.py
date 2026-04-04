from typing import Optional

import pandas as pd
from src.data.feeds.databaseAccessor import Database


def get(df: pd.DataFrame, symbol: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieve data for a specific symbol from a DataFrame.

    Parameters:
        df (pd.DataFrame): The DataFrame containing the data.
        symbol (str, optional): The symbol to filter the data by. Defaults to None.

    Returns:
        pd.DataFrame: The filtered DataFrame if a symbol is provided, otherwise the original DataFrame.
    """

    if symbol:
        sliced_df = df.copy()
        sliced_df = sliced_df[sliced_df.columns[sliced_df.columns.get_level_values(
            1) == symbol]]
        sliced_df.columns = sliced_df.columns.droplevel(1)
        return sliced_df
    else:
        if isinstance(df.columns, pd.MultiIndex) and len(df.columns.levels[1]) == 1:
            df.columns = df.columns.droplevel(1)
        return df


def get_candles(
        feed: str,
        symbols: list[str],
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Retrieve candlestick data for given symbols and timeframe

    Parameters:
        feed (str): The data source, e.g., "db".
        symbols (list[str]): List of symbols to retrieve data for.
        timeframe (str): Timeframe code (e.g., "M1").
        start_date (optional): The start date for the data retrieval.
        end_date (optional): The end date for the data retrieval.

    Returns:
        pd.DataFrame: A DataFrame containing the candlestick data with a MultiIndex for columns.
    """

    all_dataframes = []

    if feed == "db":
        for symbol in symbols:
            candles = Database.get_candles(
                symbol, timeframe, start_date, end_date)
            df = pd.DataFrame(data=candles, columns=[
                              'timestamp', 'open', 'high', 'low', 'close', 'volume'])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)

            df.columns = pd.MultiIndex.from_product([df.columns, [symbol]])

            all_dataframes.append(df)

        combined_df = pd.concat(all_dataframes, axis=1)

        return combined_df
    else:
        raise ValueError(f"Feed '{feed}' is not supported.")
