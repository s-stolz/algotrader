import pandas as pd

class CSV_Data():
    def __init__(self):
        pass

    def request_data(self, filepath, exchange):
        df = pd.read_csv(filepath, delimiter='\t')
        df.rename({'<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low', '<CLOSE>': 'close', '<VOL>': 'volume'}, axis=1, inplace=True)
        df['timestamp'] = pd.to_datetime(df['<DATE>'] + ' ' + df['<TIME>'], utc=True)
        df = df.set_index('timestamp')
        
        df.drop(['<DATE>', '<TIME>', '<TICKVOL>', '<SPREAD>'], axis=1)

        print(df)
        return df