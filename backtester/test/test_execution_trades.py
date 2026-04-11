import unittest

from domain.enums import OrderSide
from domain.types import Fill
from execution.trades import build_trades_from_fills


class TestTradeLifecycle(unittest.TestCase):
    def test_build_trades_from_buy_then_sell(self) -> None:
        fills = [
            Fill(timestamp_ms=1, symbol="AAPL", quantity=1.0, price=100.0, side=OrderSide.BUY),
            Fill(timestamp_ms=2, symbol="AAPL", quantity=1.0, price=110.0, side=OrderSide.SELL),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "AAPL")
        self.assertEqual(trades[0].entry_timestamp_ms, 1)
        self.assertEqual(trades[0].exit_timestamp_ms, 2)
        self.assertEqual(trades[0].realized_pnl, 10.0)


if __name__ == "__main__":
    unittest.main()
