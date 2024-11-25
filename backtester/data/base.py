# import data.feeds.tradingview as tv
import data.db as db
import pandas as pd
import logging

log = logging.getLogger(__name__)


def insert_market(symbol: str, exchange: str, market_type: str, min_move: float):
    fin_db = db.Database()
    fin_db.insert_market(symbol, exchange, market_type, min_move)
    fin_db.disconnect()

def request_data(feed: str, symbol: str, exchange: str):
    return
    # if feed == "tradingview":
    #     data = tv.request_data(symbol, exchange, 3000)
    
    # insert the data into the database
    fin_db = db.Database()
    fin_db.insert_candles(data, symbol, exchange)
    fin_db.disconnect()

def get(df: pd.DataFrame, symbol: str):
    sliced_df = df.copy()
    sliced_df = sliced_df[sliced_df.columns[sliced_df.columns.get_level_values(1) == symbol]]
    sliced_df.columns = sliced_df.columns.droplevel(1)
    return sliced_df

def get_candles(feed: str, symbol_ids: list[int], timeframe: int, start_date=None, end_date=None) -> pd.DataFrame:
    all_dataframes = []

    if feed == "db":
        fin_db = db.Database()

        for symbol_id in symbol_ids:
            symbol = fin_db.get_symbol(symbol_id)
            candles = fin_db.get_candles(symbol_id, timeframe, start_date, end_date)
            df = pd.DataFrame(data=candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index('timestamp', inplace=True)

            df.columns = pd.MultiIndex.from_product([df.columns, [symbol[0]]])

            all_dataframes.append(df)

        combined_df = pd.concat(all_dataframes, axis=1)
        
        return combined_df
    
def get_candles_single_symbol(feed: str, symbol_id: int, timeframe: int, start_date=None, end_date=None) -> pd.DataFrame:
    """Retrieve candle data for a single symbol and return a normal DataFrame."""
    if feed == "db":
        fin_db = db.Database()
        
        symbol = fin_db.get_symbol(symbol_id)
        
        candles = fin_db.get_candles(symbol_id, timeframe, start_date, end_date)
        
        df = pd.DataFrame(data=candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df.set_index('timestamp', inplace=True)
        
        df['symbol'] = symbol[0]
        
        return df
