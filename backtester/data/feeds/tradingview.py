from tvDatafeed import TvDatafeedLive, Interval
from decouple import config

username = config('TRADINGVIEW_USERNAME')
password = config('TRADINGVIEW_PASSWORD')

tvl = TvDatafeedLive(username, password)

def request_data(symbol: str, exchange: str, n: int):
    data = tvl.get_hist(symbol, exchange, Interval.in_1_minute, n)
    return data


'''
    # Connect to PostgreSQL database
    fin_db = db.Database(
        host=config('POSTGRES_HOST'),
        port=config('POSTGRES_PORT'),
        database="finance_data",
        user=config('POSTGRES_USER'),
        password=config('POSTGRES_PASSWORD')
    )

    pairs = ["EURUSD", "EURJPY", "EURCHF", "EURGBP", "EURAUD", "EURCAD", "EURNZD",
         "GBPUSD", "GBPCHF",  "GBPJPY", "GBPAUD", "GBPCAD", "GBPNZD",
         "AUDUSD", "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
         "NZDUSD", "NZDJPY", "NZDCHF", "NZDCAD",
         "USDJPY", "USDCHF", "USDCAD",
         "CADJPY", "CADCHF",
         "CHFJPY",
    ]    

    tvl = tv.TvDatafeedLive(tradingview_username, tradingview_password)

    for fx_pair in pairs:
        print("Get Data for: " + fx_pair)
        data = tvl.get_hist(fx_pair, 'PEPPERSTONE', tv.Interval.in_1_minute, 3000)
        print(data)
        fin_db.insert_market(fx_pair, "PEPPERSTONE", "FOREX")
        symbol_id = fin_db.get_symbol_id(fx_pair)
        fin_db.insert_candles(symbol_id, data)

    print("Get Data for: BTCUSD")
    data = tvl.get_hist("BTCUSD", "BINANCE", tv.Interval.in_1_minute, 3000)
    print(data)
    fin_db.insert_market("BTCUSD", "BINANCE", "CRYPTO")
    symbol_id = fin_db.get_symbol_id("BTCUSD")
    fin_db.insert_candles(symbol_id, data)

    print("Done...")

'''