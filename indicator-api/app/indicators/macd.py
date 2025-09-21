from re import M
import pandas as pd
import pandas_ta as ta
from itertools import product
import logging

METADATA: dict = {
    'name': 'Moving Average Convergence Divergence',
    'overlay': False,
    'warmup_params': ['slow_length', 'signal_smoothing'],
    'warmup_mode': 'sum',
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


class MACD:
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
        fast_list: list[int] = [fast_length] if isinstance(fast_length, int) else list(fast_length)
        slow_list: list[int] = [slow_length] if isinstance(slow_length, int) else list(slow_length)
        sig_list: list[int] = [signal_smoothing] if isinstance(
            signal_smoothing, int) else list(signal_smoothing)

        parameter_combinations: list[tuple[int, int, int]] = list(
            product(fast_list, slow_list, sig_list))
        symbols = data.columns.get_level_values(1).unique().to_list(
        ) if isinstance(data.columns, pd.MultiIndex) else [None]

        frames: list[pd.DataFrame] = []
        for fast, slow, signal in parameter_combinations:
            postfix = f'_{fast}_{slow}_{signal}'
            macd_df = ta.macd(data[source], fast=fast, slow=slow, signal=signal)
            macd_df.rename(columns={
                f'MACD{postfix}': f'MACD{postfix}',
                f'MACDh{postfix}': f'Histogram{postfix}',
                f'MACDs{postfix}': f'Signal{postfix}',
            }, inplace=True)
            frames.append(macd_df)

        if not frames:
            return pd.DataFrame(index=data.index)
        combined = pd.concat(frames, axis=1)
        return combined
