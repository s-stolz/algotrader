import unittest

from domain.enums import TradeDirection
from domain.types import PortfolioSnapshot, Trade
from reporting.metrics import compute_metrics


class TestReportingMetrics(unittest.TestCase):
    def test_direction_metrics_split_counts_win_rates_and_realized_pnl(self) -> None:
        trades = [
            Trade(
                trade_id="long-win",
                symbol="AAPL",
                trade_direction=TradeDirection.LONG,
                quantity=1.0,
                entry_timestamp_ms=1,
                entry_price=100.0,
                realized_pnl=10.0,
            ),
            Trade(
                trade_id="long-breakeven",
                symbol="AAPL",
                trade_direction=TradeDirection.LONG,
                quantity=1.0,
                entry_timestamp_ms=2,
                entry_price=100.0,
                realized_pnl=0.0,
            ),
            Trade(
                trade_id="short-loss",
                symbol="AAPL",
                trade_direction=TradeDirection.SHORT,
                quantity=1.0,
                entry_timestamp_ms=3,
                entry_price=100.0,
                realized_pnl=-3.0,
            ),
        ]

        metrics = compute_metrics(
            equity_curve=[
                PortfolioSnapshot(timestamp_ms=1, cash=1000.0, equity=1000.0),
                PortfolioSnapshot(timestamp_ms=2, cash=1007.0, equity=1007.0),
            ],
            trades=trades,
        )

        self.assertEqual(metrics["trade_count"], 3.0)
        self.assertEqual(metrics["long_trade_count"], 2.0)
        self.assertEqual(metrics["short_trade_count"], 1.0)
        self.assertEqual(metrics["long_win_rate_pct"], 50.0)
        self.assertEqual(metrics["short_win_rate_pct"], 0.0)
        self.assertEqual(metrics["long_realized_pnl"], 10.0)
        self.assertEqual(metrics["short_realized_pnl"], -3.0)

    def test_direction_win_rates_are_zero_without_direction_trades(self) -> None:
        metrics = compute_metrics(
            equity_curve=[
                PortfolioSnapshot(timestamp_ms=1, cash=1000.0, equity=1000.0),
            ],
            trades=[],
        )

        self.assertEqual(metrics["trade_count"], 0.0)
        self.assertEqual(metrics["long_trade_count"], 0.0)
        self.assertEqual(metrics["short_trade_count"], 0.0)
        self.assertEqual(metrics["long_win_rate_pct"], 0.0)
        self.assertEqual(metrics["short_win_rate_pct"], 0.0)
        self.assertEqual(metrics["long_realized_pnl"], 0.0)
        self.assertEqual(metrics["short_realized_pnl"], 0.0)

    def test_trade_count_still_reflects_closed_trades_without_equity_curve(self) -> None:
        metrics = compute_metrics(
            equity_curve=[],
            trades=[
                Trade(
                    trade_id="short-win",
                    symbol="AAPL",
                    trade_direction=TradeDirection.SHORT,
                    quantity=1.0,
                    entry_timestamp_ms=1,
                    entry_price=100.0,
                    realized_pnl=2.0,
                ),
            ],
        )

        self.assertEqual(metrics["trade_count"], 1.0)
        self.assertEqual(metrics["short_trade_count"], 1.0)
        self.assertEqual(metrics["short_win_rate_pct"], 100.0)
        self.assertEqual(metrics["short_realized_pnl"], 2.0)


if __name__ == "__main__":
    unittest.main()
