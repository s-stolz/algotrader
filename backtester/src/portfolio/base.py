import pandas as pd
import numpy as np


class Portfolio:
    initial_balance = 1_000
    volume = 1_000

    def __init__(self, data: pd.DataFrame, positions: pd.DataFrame):
        self.positions = positions
        self.strat_rets = self.calculate_returns(data, positions)
        self.stats = self.calculate_stats()

    def get_stats(self):
        return self.stats
    
    def calculate_stats(self) -> pd.DataFrame:
        """Calculate portfolio statistics per symbol."""
        profit_percentage = self.strat_rets.sum() * 100

        profit_money = profit_percentage / 100 * self.volume

        #trades = (self.positions.diff() == 1).sum()

        # Combine all statistics in a DataFrame
        stats = pd.DataFrame({
            'Profit (%)': profit_percentage.round(2),
            'Profit ($)': profit_money.round(2),
            #'Number of Trades': trades
        })

        return stats
    
    @staticmethod
    def calculate_returns(data: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
        entry_price = data['open'].shift(-1)
        exit_price = data['open'].shift(-2)
        returns = (exit_price - entry_price) / entry_price

        strat_rets = (returns * positions).fillna(0)
        return strat_rets
    
    @staticmethod
    def signals_to_positions(buy_signals: pd.DataFrame, sell_signals: pd.DataFrame) -> pd.DataFrame:
        signals = np.where(buy_signals, 1, 
                        np.where(sell_signals, -1, np.nan))

        ffill_signals = pd.DataFrame(signals, columns=buy_signals.columns, index=buy_signals.index)
        ffill_signals = ffill_signals.ffill().fillna(-1).astype(int)
        positions = (ffill_signals + 1) // 2
        return positions.astype(np.bool_)

    @classmethod
    def from_signals(cls, data: pd.DataFrame, buy_signals: pd.DataFrame, sell_signals: pd.DataFrame) -> pd.DataFrame:
        positions = cls.signals_to_positions(buy_signals, sell_signals)

        return cls(data, positions)
    