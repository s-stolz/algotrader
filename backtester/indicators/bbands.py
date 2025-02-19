import pandas as pd
import pandas_ta as ta
import logging


class BBANDS:
    def __init__(self, data: pd.DataFrame, length: int, source: str, std: float, ma_mode: str) -> None:
        self.data = data
        self.length = length
        self.source = source
        self.std = std
        self.ma_mode = ma_mode

    @staticmethod
    def info() -> dict:
        return {
            'name': 'Bollinger Bands',
            'overlay': True,
            'outputs': {
                'lower': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#089981'
                    },
                },
                'mid': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#2962ff'
                    },
                },
                'upper': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 2,
                        'color': '#f23645'
                    },
                },
            }, 
            'parameters': {
                'length': {
                    'type': 'int',
                    'default': 20,
                    'min': 1,
                    'max': 1e6,
                    'step': 1
                },
                'ma_mode': {
                    'type': 'string',
                    'default': 'SMA',
                    'options': ['SMA', 'EMA']
                },
                'std': {
                    'type': 'float',
                    'default': 2,
                    'min': 0,
                    'max': 1e6,
                    'step': 1
                },
                'source': {
                    'type': 'string',
                    'default': 'close',
                    'options': ['close', 'open', 'high', 'low']
                }
            },
        }

    def run(self) -> pd.DataFrame:
        """Calculate the Bollinger Bands"""
        std_str = f'{self.std}.0' if self.std % 1 == 0 else str(self.std)
        postfix = f'_{self.length}_{std_str}'
        bbands = ta.bbands(self.data[self.source],
                           self.length, self.std, mamode=self.ma_mode)
        
        bbands = bbands.drop(columns=[f'BBB{postfix}', f'BBP{postfix}'])
        bbands.rename(columns={
            f'BBL{postfix}': 'lower',
            f'BBM{postfix}': 'mid',
            f'BBU{postfix}': 'upper',
        }, inplace=True)

        return bbands
