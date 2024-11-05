import pandas as pd

class SMA:
    def __init__(self, data: pd.DataFrame, windows: list[int]) -> None:
        self.data = data
        self.windows = windows

    def run(self) -> pd.DataFrame:
        """Calculate the Simple Moving Average"""
        sma_results = []

        for window in self.windows:
            sma_window = self.data.rolling(window=window).mean()
            sma_window.columns = pd.MultiIndex.from_product([[f"SMA_{window}"], sma_window.columns])
            sma_results.append(sma_window)

        final_sma_df = pd.concat(sma_results, axis=1)

        return final_sma_df