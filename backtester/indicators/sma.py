import pandas as pd
import math
import logging


class SMA:
    def __init__(self, data: pd.DataFrame, window: int, source: str) -> None:
        self.data = data
        self.window = window
        self.source = source

    @staticmethod
    def info() -> dict:
        return {
            'name': 'Simple Moving Average',
            'overlay': True,
            'outputs': {
                'sma': {
                    'type': 'line',
                    'plotOptions': {
                        'lineWidth': 3,
                        'color': '#FCFC4E'
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
            }
        }

    def run(self) -> pd.DataFrame:
        """Calculate the Simple Moving Average"""
        sma = self.data[self.source].rolling(
            window=self.window).mean().to_frame(name='value')
        return sma

    def run_multi(self) -> pd.DataFrame:
        """Calculate the Simple Moving Average"""
        sma_results = []

        for window in self.windows:
            sma_window = self.data[self.source].rolling(window=window).mean()
            sma_window.columns = pd.MultiIndex.from_product(
                [[f"SMA_{window}"], sma_window.columns])
            sma_results.append(sma_window)

        final_sma_df = pd.concat(sma_results, axis=1)

        return final_sma_df
