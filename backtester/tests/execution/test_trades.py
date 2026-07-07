import unittest

from domain.enums import ExitReason, OrderSide, TradeDirection
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
        self.assertEqual(trades[0].trade_direction, TradeDirection.LONG)
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

    def test_short_round_trip_opens_from_sell_and_closes_from_buy(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.SELL,
                fees=1.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=90.0,
                side=OrderSide.BUY,
                fees=2.0,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].trade_direction, TradeDirection.SHORT)
        self.assertEqual(trades[0].quantity, 1.0)
        self.assertEqual(trades[0].entry_timestamp_ms, 1)
        self.assertEqual(trades[0].entry_price, 100.0)
        self.assertEqual(trades[0].exit_timestamp_ms, 2)
        self.assertEqual(trades[0].exit_price, 90.0)
        self.assertEqual(trades[0].fees, 3.0)
        self.assertEqual(trades[0].realized_pnl, 7.0)

    def test_short_reduction_closes_only_reduced_quantity(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=2.0,
                price=100.0,
                side=OrderSide.SELL,
                fees=2.0,
                stop_loss_price=105.0,
                take_profit_price=90.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=90.0,
                side=OrderSide.BUY,
                fees=1.0,
            ),
            Fill(
                timestamp_ms=3,
                symbol="AAPL",
                quantity=1.0,
                price=80.0,
                side=OrderSide.BUY,
                fees=1.0,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].trade_direction, TradeDirection.SHORT)
        self.assertEqual(trades[0].quantity, 1.0)
        self.assertEqual(trades[0].fees, 2.0)
        self.assertEqual(trades[0].realized_pnl, 8.0)
        self.assertEqual(trades[0].stop_loss_price, 105.0)
        self.assertEqual(trades[0].take_profit_price, 90.0)
        self.assertEqual(trades[1].trade_direction, TradeDirection.SHORT)
        self.assertEqual(trades[1].quantity, 1.0)
        self.assertEqual(trades[1].fees, 2.0)
        self.assertEqual(trades[1].realized_pnl, 18.0)
        self.assertEqual(trades[1].stop_loss_price, 105.0)
        self.assertEqual(trades[1].take_profit_price, 90.0)

    def test_direction_flip_closes_and_opens_with_pro_rata_fees(self) -> None:
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
                quantity=2.0,
                price=110.0,
                side=OrderSide.SELL,
                fees=4.0,
            ),
            Fill(
                timestamp_ms=3,
                symbol="AAPL",
                quantity=1.0,
                price=90.0,
                side=OrderSide.BUY,
                fees=1.0,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].trade_direction, TradeDirection.LONG)
        self.assertEqual(trades[0].quantity, 1.0)
        self.assertEqual(trades[0].fees, 3.0)
        self.assertEqual(trades[0].realized_pnl, 7.0)
        self.assertEqual(trades[1].trade_direction, TradeDirection.SHORT)
        self.assertEqual(trades[1].quantity, 1.0)
        self.assertEqual(trades[1].entry_timestamp_ms, 2)
        self.assertEqual(trades[1].entry_price, 110.0)
        self.assertEqual(trades[1].fees, 3.0)
        self.assertEqual(trades[1].realized_pnl, 17.0)

    def test_sell_fill_exit_reason_is_copied_to_closed_trade(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.BUY,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=95.0,
                side=OrderSide.SELL,
                exit_reason=ExitReason.STOP_LOSS,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(trades[0].exit_reason, ExitReason.STOP_LOSS)

    def test_entry_fill_planned_protective_prices_are_copied_to_closed_trade(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.BUY,
                stop_loss_price=95.0,
                take_profit_price=110.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=104.0,
                side=OrderSide.SELL,
                exit_reason=ExitReason.SIGNAL,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(trades[0].exit_reason, ExitReason.SIGNAL)
        self.assertEqual(trades[0].exit_price, 104.0)
        self.assertEqual(trades[0].stop_loss_price, 95.0)
        self.assertEqual(trades[0].take_profit_price, 110.0)

    def test_planned_protective_prices_follow_average_entry_after_scale_in(self) -> None:
        fills = [
            Fill(
                timestamp_ms=1,
                symbol="AAPL",
                quantity=1.0,
                price=100.0,
                side=OrderSide.BUY,
                stop_loss_price=95.0,
                take_profit_price=110.0,
            ),
            Fill(
                timestamp_ms=2,
                symbol="AAPL",
                quantity=1.0,
                price=120.0,
                side=OrderSide.BUY,
                stop_loss_price=114.0,
                take_profit_price=132.0,
            ),
            Fill(
                timestamp_ms=3,
                symbol="AAPL",
                quantity=2.0,
                price=130.0,
                side=OrderSide.SELL,
                exit_reason=ExitReason.SIGNAL,
            ),
        ]

        trades = build_trades_from_fills(fills)

        self.assertEqual(trades[0].entry_price, 110.0)
        self.assertEqual(trades[0].stop_loss_price, 104.5)
        self.assertEqual(trades[0].take_profit_price, 121.0)

    def test_opening_sell_remains_open_until_short_cover(self) -> None:
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

        self.assertEqual(build_trades_from_fills(fills), [])


if __name__ == "__main__":
    unittest.main()
