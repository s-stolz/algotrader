import pandas as pd
import pandas_ta as ta

METADATA: dict = {
    'name': 'Relative Strength Index',
    'overlay': False,
    'warmup_params': ['length'],
    'outputs': {
        'rsi': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#7E57C2'
            },
        }
    },
    'parameters': {
        'length': {
            'type': 'int',
            'default': 14,
            'min': 1,
            'max': 1e6,  # Use a large number instead of infinity
            'step': 1
        },
        'source': {
            'type': 'string',
            'default': 'close',
            'options': ['close', 'open', 'high', 'low']
        }
    },
}


class RSI:
    @staticmethod
    def run(data: pd.DataFrame, source: str = 'close', length: int = 14) -> pd.DataFrame:
        """Calculate the Simple Moving Average"""
        rsi = pd.DataFrame(None, index=data.index, columns=['rsi'])
        rsi['rsi'] = ta.rsi(data[source], length=length).values

        return rsi

    @staticmethod
    def run_multi(
            data: pd.DataFrame, source: str = 'close', length: list[int] | int = 14) -> pd.DataFrame:
        """Calculate the Simple Moving Average"""
        length = [length] if isinstance(length, int) else length
        symbols = data.columns.get_level_values(1).unique().to_list()
        columns = pd.MultiIndex.from_product([[f'RSI_{x}' for x in length], symbols])
        rsi = pd.DataFrame(None, index=data.index, columns=columns)

        for symbol in symbols:
            for l in length:
                rsi[(f'RSI_{l}', symbol)] = ta.rsi(data[source][symbol], length=l).values

        return rsi
