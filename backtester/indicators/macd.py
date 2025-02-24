import pandas as pd
import pandas_ta as ta
import logging


class MACD:
    def __init__(self, data: pd.DataFrame, fast_length: int, slow_length: int, 
                 source: str, signal_smoothing: int) -> None:
        self.data = data
        self.fast_length = fast_length
        self.slow_lenght= slow_length
        self.source = source
        self.signal_smoothing = signal_smoothing

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

    def run(self) -> pd.DataFrame:
        """Calculate the Moving Average Convergence Divergence"""
        postfix = f'_{self.fast_length}_{self.slow_lenght}_{self.signal_smoothing}'

        macd = ta.macd(self.data[self.source], 
                       fast=self.fast_length, 
                       slow=self.slow_lenght, 
                       signal=self.signal_smoothing
                       )

        macd.rename(columns={
            f'MACD{postfix}': 'MACD',
            f'MACDh{postfix}': 'Histogram',
            f'MACDs{postfix}': 'Signal',
        }, inplace=True)

        return macd
