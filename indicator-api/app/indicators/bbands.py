import pandas as pd
import pandas_ta as ta
import logging


METADATA: dict = {
    'name': 'Bollinger Bands',
    'overlay': True,
    'warmup_params': ['length'],
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
            'step': 1
        },
        'ma_mode': {
            'type': 'string',
            'default': 'SMA',
            'options': ['SMA', 'EMA']
        },
        'lower_std': {
            'type': 'float',
            'default': 1.0,
            'min': 0,
            'step': .1
        },
        'upper_std': {
            'type': 'float',
            'default': 2.0,
            'min': 0,
            'step': .1
        },
        'source': {
            'type': 'string',
            'default': 'close',
            'options': ['close', 'open', 'high', 'low']
        }
    }
}


class BBANDS:
    @staticmethod
    def run(data: pd.DataFrame, length: int = 20, source: str = 'close', lower_std: float = 2.0,
            upper_std: float = 2.0, ma_mode: str = 'SMA') -> pd.DataFrame:
        """Calculate the Bollinger Bands"""
        postfix = f'_{length}_{lower_std}_{upper_std}'
        bbands = ta.bbands(data[source],
                           length, lower_std, upper_std, mamode=ma_mode)

        if bbands is None:
            logging.error(
                "Bollinger Bands calculation failed. Check the input data and parameters.")
            import pandas as _pd
            return _pd.DataFrame(index=data.index, columns=['lower', 'mid', 'upper'])

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
