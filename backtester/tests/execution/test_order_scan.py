"""Close-time commands are merged onto the minute execution clock."""

import unittest

import numpy as np
from domain.enums import OrderSide
from domain.orders import LimitOrder, OrderAction, OrderCommand
from execution.order_scan import scan_orders
from execution.orders import OrderExecutionConfig


class OrderScanTests(unittest.TestCase):
    def test_command_cannot_fill_before_effective_boundary(self):
        order = LimitOrder("entry", OrderSide.BUY, 95, 2)
        result = scan_orders(
            symbol="TEST",
            timestamp_ms=[0, 60_000, 120_000],
            ohlc=np.array(
                [[100, 101, 90, 100], [100, 101, 99, 100], [94, 96, 93, 95]], dtype=float
            ),
            commands=[OrderCommand(60_000, OrderAction.SUBMIT, "entry", order)],
            end_ms=180_000,
            config=OrderExecutionConfig(),
        )
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].timestamp_ms, 120_000)
        np.testing.assert_array_equal(result.executed_delta, [0, 0, 2])
        np.testing.assert_array_equal(result.executed_notional, [0, 0, 188])

    def test_update_keeps_id_and_changes_future_fill_price(self):
        first = LimitOrder("entry", OrderSide.BUY, 90, 1)
        updated = LimitOrder("entry", OrderSide.BUY, 99, 1)
        result = scan_orders(
            symbol="TEST",
            timestamp_ms=[0, 60_000],
            ohlc=np.array([[100, 101, 95, 100], [100, 101, 98, 100]], dtype=float),
            commands=[
                OrderCommand(0, OrderAction.SUBMIT, "entry", first),
                OrderCommand(60_000, OrderAction.UPDATE, "entry", updated),
            ],
            end_ms=120_000,
            config=OrderExecutionConfig(),
        )
        self.assertEqual(result.fills[0].price, 99)
        self.assertEqual(result.fills[0].timestamp_ms, 60_000)

    def test_pending_order_expires_at_run_end(self):
        order = LimitOrder("entry", OrderSide.BUY, 90, 1)
        result = scan_orders(
            symbol="TEST",
            timestamp_ms=[0],
            ohlc=np.array([[100, 101, 95, 100]], dtype=float),
            commands=[OrderCommand(0, OrderAction.SUBMIT, "entry", order)],
            end_ms=60_000,
            config=OrderExecutionConfig(),
        )
        self.assertFalse(result.fills)
        self.assertEqual(result.events[-1]["outcome"], "run_end_expired")
