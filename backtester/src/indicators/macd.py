import pandas as pd
import pandas_ta as ta
from itertools import product
import logging


class MACD:
    @staticmethod
    def info() -> dict:
        return {
            'name': 'Moving Average Convergence Divergence',
            'overlay': False,
            'outputs': {
                'Histogram': {
                    'type': 'histogram',
                    'plotOptions': {
                        'color': '#089981',
                        'priceFormat': {
                            'minMove': 0.00001
                        }
                    },
                },
                'MACD': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#2962ff',
                        'priceFormat': {
                            'minMove': 0.00001
                        }
                    },
                },
                'Signal': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#f23645',
                        'priceFormat': {
                            'minMove': 0.00001
                        }
                    },
                },
            }, 
            'parameters': {
                'fast_length': {
                    'type': 'int',
                    'default': 12,
                    'min': 1,
                    'max': 1e6,
                    'step': 1
                },
                'slow_length': {
                    'type': 'int',
                    'default': 26,
                    'min': 1,
                    'max': 1e6,
                    'step': 1
                },
                'source': {
                    'type': 'string',
                    'default': 'close',
                    'options': ['close', 'open', 'high', 'low']
                },
                'signal_smoothing': {
                    'type': 'int',
                    'default': 9,
                    'min': 1,
                    'max': 1e6,
                    'step': 1
                },
            },
        }

    @staticmethod
    def run(data: pd.DataFrame, fast_length: int, slow_length: int, 
                 source: str, signal_smoothing: int) -> pd.DataFrame:
        """Calculate the Moving Average Convergence Divergence"""
        postfix = f'_{fast_length}_{slow_length}_{signal_smoothing}'
        macd = ta.macd(data[source], 
                       fast=fast_length, 
                       slow=slow_length, 
                       signal=signal_smoothing
                       )

        macd.rename(columns={
            f'MACD{postfix}': 'MACD',
            f'MACDh{postfix}': 'Histogram',
            f'MACDs{postfix}': 'Signal',
        }, inplace=True)

        return macd

    @staticmethod
    def run_multi(data: pd.DataFrame, fast_length: int | list[int], 
                  slow_length: int | list[int], source: str, 
                  signal_smoothing: int | list[int]) -> pd.DataFrame:
        """
        Calculat the Moving Average Convergence Divergence with parameter variations
        """
        # TODO: FIX BUGs
        fast_length = [fast_length] if type(fast_length) == int else fast_length
        slow_length = [slow_length] if type(slow_length) == int else slow_length
        signal_smoothing = [signal_smoothing] if type(signal_smoothing) == int else signal_smoothing

        parameter_combinations = list(product(fast_length, slow_length, signal_smoothing))
        #columns = pd.MultiIndex.from_product([[f"MACD_{fast}_{slow}_{signal}" for fast, slow, signal in parameter_combinations], symbols])
        symbols = data.columns.get_level_values(1).unique().to_list()

        macd = pd.DataFrame(None, index=data.index)

        for s in symbols:
            for fast, slow, signal in parameter_combinations:
                print(fast, slow, signal)
                post = f'_{fast}_{slow}_{signal}'
                # macd[f'MACD'+post], macd[f'MACDh'+post], macd[f'MACDs'+post]
                macd = ta.macd(data[source], 
                    fast=fast, 
                    slow=slow, 
                    signal=signal
                    )
                print(macd)

        return macd
        