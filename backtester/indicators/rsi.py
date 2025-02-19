import pandas as pd
import pandas_ta as ta
import logging


class RSI:
    def __init__(self, data: pd.DataFrame, length: int, source: str) -> None:
        self.data = data
        self.length = length
        self.source = source

    @staticmethod
    def info() -> dict:
        return {
            'name': 'Relative Strength Index',
            'overlay': False,
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

    def run(self) -> pd.DataFrame:
        """Calculate the Relative Strength Index"""
        postfix = f'_{self.length}'
        rsi = ta.rsi(self.data[self.source], length=self.length).to_frame()
        rsi.rename(columns={f'RSI{postfix}': 'rsi'}, inplace=True)
        return rsi

    # def run_multi(self) -> pd.DataFrame:
    #     """Calculate the Simple Moving Average"""
    #     sma_results = []

    #     for window in self.windows:
    #         sma_window = self.data[self.source].rolling(window=window).mean()
    #         sma_window.columns = pd.MultiIndex.from_product(
    #             [[f"SMA_{window}"], sma_window.columns])
    #         sma_results.append(sma_window)

    #     final_sma_df = pd.concat(sma_results, axis=1)

    #     return final_sma_df
