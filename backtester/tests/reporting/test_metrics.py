import unittest

from domain.enums import TradeDirection
from domain.types import PortfolioSnapshot, Trade
from reporting.metrics import compute_metrics


class TestBacktestMetrics(unittest.TestCase):
    def test_direction_metrics_use_closed_trade_realized_pnl(self) -> None:
        metrics = compute_metrics(
            equity_curve=[
                PortfolioSnapshot(
                    timestamp_ms=1,
                    cash=10_000.0,
                    equity=10_000.0,
                    positions={},
                ),
                PortfolioSnapshot(
                    timestamp_ms=2,
                    cash=10_005.0,
                    equity=10_005.0,
                    positions={},
                ),
            ],
            trades=[
                Trade(
                    trade_id="long-win",
                    symbol="AAPL",
                    trade_direction=TradeDirection.LONG,
                    quantity=1.0,
                    entry_timestamp_ms=1,
                    entry_price=100.0,
                    exit_timestamp_ms=2,
                    exit_price=103.0,
                    realized_pnl=2.5,
                    fees=0.5,
                ),
                Trade(
                    trade_id="short-loss",
                    symbol="AAPL",
                    trade_direction=TradeDirection.SHORT,
                    quantity=1.0,
                    entry_timestamp_ms=3,
                    entry_price=98.0,
                    exit_timestamp_ms=4,
                    exit_price=99.0,
                    realized_pnl=-1.25,
                    fees=0.25,
                ),
                Trade(
                    trade_id="short-break-even",
                    symbol="AAPL",
                    trade_direction=TradeDirection.SHORT,
                    quantity=1.0,
                    entry_timestamp_ms=5,
                    entry_price=95.0,
                    exit_timestamp_ms=6,
                    exit_price=95.0,
                    realized_pnl=0.0,
                    fees=0.0,
                ),
            ],
        )

        self.assertEqual(metrics["trade_count"], 3.0)
        self.assertEqual(metrics["long_trade_count"], 1.0)
        self.assertEqual(metrics["short_trade_count"], 2.0)
        self.assertEqual(metrics["long_win_rate_pct"], 100.0)
        self.assertEqual(metrics["short_win_rate_pct"], 0.0)
        self.assertEqual(metrics["long_realized_pnl"], 2.5)
        self.assertEqual(metrics["short_realized_pnl"], -1.25)


if __name__ == "__main__":
    unittest.main()
