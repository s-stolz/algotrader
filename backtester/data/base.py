# import data.feeds.tradingview as tv
import data.db as db


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

    