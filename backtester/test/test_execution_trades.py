import unittest

from domain.enums import ExitReason, OrderSide
from domain.types import Fill
from execution.trades import build_trades_from_fills


class TestTradeLifecycle(unittest.TestCase):
    def test_build_trades_from_buy_then_sell_is_net_of_fees(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.BUY,
                fees=1.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=110.0,
                side=OrderSide.SELL,
                fees=2.0,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "AAPL")
        self.assertEqual(trades[0].entry_timestamp_ms, 1)
        self.assertEqual(trades[0].exit_timestamp_ms, 2)
        self.assertEqual(trades[0].fees, 3.0)
        self.assertGreaterEqual(trades[0].fees, 0.0)
        self.assertEqual(trades[0].realized_pnl, 7.0)
        self.assertEqual(trades[0].exit_reason, ExitReason.SIGNAL)

    def test_partial_exits_allocate_entry_and_exit_fees(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=2.0,
                price=100.0,
                side=OrderSide.BUY,
                fees=2.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=110.0,
                side=OrderSide.SELL,
                fees=1.0,
            ),
            Fill(
                timestamp_ms=3,
                symbol="AAPL",
                quantity=1.0,
                price=120.0,
                side=OrderSide.SELL,
                fees=1.0,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].fees, 2.0)
        self.assertEqual(trades[0].realized_pnl, 8.0)
        self.assertEqual(trades[1].fees, 2.0)
        self.assertEqual(trades[1].realized_pnl, 18.0)

    def test_sell_without_open_long_is_rejected(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.SELL,
                fees=0.0,
            )
        ]

        with self.assertRaises(ValueError):
            build_trades_from_fills(fills)


if __name__ == "__main__":
    unittest.main()
