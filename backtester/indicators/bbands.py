import pandas as pd
import pandas_ta as ta
import logging


class BBANDS:
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
                    'step': .1
                },
                'source': {
                    'type': 'string',
                    'default': 'close',
                    'options': ['close', 'open', 'high', 'low']
                }
            },
        }

    @staticmethod
    def run(data: pd.DataFrame, length: int = 20, source: str = 'close', std: float = 2.0, ma_mode: str = 'SMA') -> pd.DataFrame:
        """Calculate the Bollinger Bands"""
        std_str = f'{std}.0' if std % 1 == 0 else str(std)
        postfix = f'_{length}_{std_str}'
        bbands = ta.bbands(data[source],
                           length, std, mamode=ma_mode)
        
        bbands = bbands.drop(columns=[f'BBB{postfix}', f'BBP{postfix}'])
        bbands.rename(columns={
            f'BBL{postfix}': 'lower',
            f'BBM{postfix}': 'mid',
            f'BBU{postfix}': 'upper',
        }, inplace=True)

        return bbands


    @staticmethod
    def run_multi():
        # TODO
        pass