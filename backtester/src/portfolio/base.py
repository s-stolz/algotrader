import numpy as np
import pandas as pd


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
        compounded_return = (1.0 + self.strat_rets).prod() - 1.0
        profit_percentage = compounded_return * 100.0
        profit_money = compounded_return * self.volume

        stats = pd.DataFrame(
            {
                "Profit (%)": profit_percentage,
                "Profit ($)": profit_money,
            }
        )
        return stats

    @staticmethod
    def calculate_returns(data: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return pd.DataFrame(index=data.index, columns=positions.columns).fillna(0.0)

        # Use first available price column (typically "open" in this backtester flow).
        price = data.iloc[:, 0]
        entry_price = price.shift(-1)
        exit_price = price.shift(-2)
        returns = (exit_price - entry_price) / entry_price

        aligned_positions = positions.reindex(index=data.index).fillna(False).astype(float)
        strat_rets = aligned_positions.mul(returns, axis=0).fillna(0.0)
        return strat_rets

    @staticmethod
    def signals_to_positions(
        buy_signals: pd.DataFrame,
        sell_signals: pd.DataFrame,
    ) -> pd.DataFrame:
        signals = np.where(
            buy_signals,
            1,
            np.where(sell_signals, -1, np.nan),
        )

        ffill_signals = pd.DataFrame(
            signals,
            columns=buy_signals.columns,
            index=buy_signals.index,
        )
        ffill_signals = ffill_signals.ffill().fillna(-1).astype(int)
        positions = (ffill_signals + 1) // 2
        return positions.astype(np.bool_)

    @classmethod
    def from_signals(
        cls,
        data: pd.DataFrame,
        buy_signals: pd.DataFrame,
        sell_signals: pd.DataFrame,
    ) -> "Portfolio":
        positions = cls.signals_to_positions(buy_signals, sell_signals)
        if len(data.columns) == len(positions.columns):
            positions.columns = data.columns

        return cls(data, positions)
