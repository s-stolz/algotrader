# import data.feeds.tradingview as tv
from data.db import Database
import pandas as pd
import logging

log = logging.getLogger(__name__)

def insert_market(symbol: str, exchange: str, market_type: str, min_move: float):
    Database.insert_market(symbol, exchange, market_type, min_move)

def request_data(feed: str, symbol: str, exchange: str):
    return
    # if feed == "tradingview":
    #     data = tv.request_data(symbol, exchange, 3000)
    
    # insert the data into the database
    Database.insert_candles(data, symbol, exchange)

def get(df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
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
        sliced_df = sliced_df[sliced_df.columns[sliced_df.columns.get_level_values(1) == symbol]]
        sliced_df.columns = sliced_df.columns.droplevel(1)
        return sliced_df
    else:
        if isinstance(df.columns, pd.MultiIndex) and len(df.columns.levels[1]) == 1:
            df.columns = df.columns.droplevel(1)
        return df
    
def get_symbol_id(symbols: list[str]) -> list[int]:
    """
    Retrieve the unique identifier for each symbol in the provided list.
    Args:
        symbols (list[str]): A list of symbol strings for which to retrieve IDs.
    Returns:
        list[int]: A list of unique identifiers corresponding to the provided symbols.
    """
    symbol_ids = []
    for symbol in symbols:
        symbol_id = Database.get_symbol_id(symbol)
        if symbol_id:
            symbol_ids.append(symbol_id)
    return symbol_ids

def get_candles(feed: str, symbol_ids: list[int], timeframe: int, start_date=None, end_date=None) -> pd.DataFrame:
    """
    Retrieve candlestick data for given symbols and timeframe
    
    Parameters:
        feed (str): The data source, e.g., "db".
        symbol_ids (list[int]): List of symbol IDs to retrieve data for.
        timeframe (int): The timeframe for the candlestick data.
        start_date (optional): The start date for the data retrieval.
        end_date (optional): The end date for the data retrieval.
        
    Returns:
        pd.DataFrame: A DataFrame containing the candlestick data with a MultiIndex for columns.
    """
    
    all_dataframes = []

    if feed == "db":
        for symbol_id in symbol_ids:
            symbol = Database.get_symbol(symbol_id)

            if symbol is None:
                raise ValueError(f"symbol_id {symbol_id} does not exist!")

            candles = Database.get_candles(symbol_id, timeframe, start_date, end_date)
            df = pd.DataFrame(data=candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index('timestamp', inplace=True)

            df.columns = pd.MultiIndex.from_product([df.columns, [symbol[0]]])

            all_dataframes.append(df)

        combined_df = pd.concat(all_dataframes, axis=1)
        
        return combined_df
