import pandas as pd
import math
import logging


class SMA:
    @staticmethod
    def info() -> dict:
        return {
            'name': 'Simple Moving Average',
            'overlay': True,
            'outputs': {
                'sma': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#FCFC4E'
                    },
                }
            },
            'parameters': {
                'window': {
                    'type': 'int',
                    'default': 20,
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
    
    @staticmethod
    def run(data: pd.DataFrame, source: str = 'close', window: int = 20):
        sma = pd.DataFrame(None, index=data.index, columns=['sma'])
        sma['sma'] = data[source].rolling(window=window).mean().values

        return sma
    
    @staticmethod
    def run_multi(data: pd.DataFrame, source: str = 'close', window: int | list[int] = 20):
        window = [window] if type(window) == int else window
        symbols = data.columns.get_level_values(1).unique().to_list()
        columns = pd.MultiIndex.from_product([[f"SMA_{w}" for w in window], symbols])
        sma = pd.DataFrame(None, index=data.index, columns=columns)

        for symbol in symbols:
            for w in window:
                sma[(f'SMA_{w}', symbol)] = data[source].rolling(window=w).mean().values

        return sma
