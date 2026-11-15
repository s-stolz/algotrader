"""Behavioral coverage for persistent minute order execution."""

import unittest

from domain.enums import OrderSide
from domain.orders import (
    IntrabarExecutionPolicy,
    LimitOrder,
    OrderAction,
    OrderCommand,
    OrderProtection,
    TakeProfitTier,
)
from execution.orders import OrderExecutionConfig, OrderExecutionState, execute_minute


class OrderExecutionTests(unittest.TestCase):
    def state(self, *orders):
        state = OrderExecutionState()
        for order in orders:
            state.command(OrderCommand(60_000, OrderAction.SUBMIT, order.order_id, order))
        return state

    def minute(self, state, prices, **kwargs):
        return execute_minute(
            state,
            symbol="TEST",
            timestamp_ms=60_000,
            prices=prices,
            config=OrderExecutionConfig(**kwargs),
        )

    def test_spread_controls_touch_and_limit_bounds_slippage(self):
        state = self.state(LimitOrder("buy", OrderSide.BUY, 100, 2))
        missed = self.minute(state, (101, 102, 100, 101), spread=1)
        self.assertFalse(missed.fills)
        filled = self.minute(state, (98, 102, 97, 101), spread=1, slippage_bps=200)
        self.assertEqual(filled.fills[0].price, 100)
        self.assertEqual(filled.position, 2)
        self.assertFalse(state.fills)

    def test_oco_competing_entries_and_strict_ambiguity(self):
        state = self.state(
            LimitOrder("buy", OrderSide.BUY, 95, 1, oco_group="entry"),
            LimitOrder("sell", OrderSide.SELL, 105, 1, oco_group="entry"),
        )
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.minute(state, (100, 106, 94, 100), policy=IntrabarExecutionPolicy.ERROR)
        result = self.minute(state, (100, 106, 94, 100))
        self.assertEqual(len(result.fills), 1)
        self.assertFalse(result.active)
        self.assertEqual(result.ambiguous_minutes, 1)

    def test_partial_profit_keeps_stop_and_stop_cancels_entries(self):
        protection = OrderProtection(90, (TakeProfitTier(110, quantity=2),))
        state = self.state(
            LimitOrder("buy", OrderSide.BUY, 100, 5, protection=protection),
            LimitOrder("lower", OrderSide.BUY, 80, 1),
        )
        state = self.minute(state, (100, 111, 99, 110))
        self.assertEqual(state.position, 3)
        self.assertEqual(state.stop_price, 90)
        state = self.minute(state, (89, 90, 79, 85))
        self.assertEqual(state.position, 0)
        self.assertFalse(state.active)
        self.assertEqual([fill.quantity for fill in state.fills], [5, 2, 3])

    def test_expiry_is_exclusive_and_inactive_update_is_noop(self):
        order = LimitOrder("buy", OrderSide.BUY, 100, 1, expires_at_ms=60_000)
        state = self.minute(self.state(order), (99, 101, 98, 100))
        self.assertFalse(state.fills)
        state.command(OrderCommand(120_000, OrderAction.UPDATE, "buy", order))
        self.assertFalse(state.active)
        self.assertEqual(state.events[-1]["outcome"], "inactive_noop")

    def test_constraint_cancels_whole_second_order(self):
        state = self.state(
            LimitOrder("first", OrderSide.BUY, 100, 2), LimitOrder("second", OrderSide.BUY, 100, 2)
        )
        result = self.minute(state, (100, 101, 99, 100), max_position_quantity=3)
        self.assertEqual(result.position, 2)
        self.assertEqual(result.events[-1]["outcome"], "constraint_cancelled")

    def test_entry_cannot_take_profit_before_it_exists(self):
        state = self.state(
            LimitOrder(
                "buy",
                OrderSide.BUY,
                95,
                1,
                protection=OrderProtection(90, (TakeProfitTier(105, quantity=1),)),
            )
        )
        conservative = self.minute(state, (100, 106, 94, 100))
        optimistic = self.minute(
            state, (100, 106, 94, 100), policy=IntrabarExecutionPolicy.OPTIMISTIC
        )
        self.assertEqual(conservative.position, 1)
        self.assertEqual(optimistic.position, 0)
        self.assertEqual(len(optimistic.fills), 2)

    def test_reduce_only_never_reverses(self):
        state = self.state(
            LimitOrder("buy", OrderSide.BUY, 100, 2),
            LimitOrder("exit", OrderSide.SELL, 110, 5, reduce_only=True),
        )
        result = self.minute(state, (100, 111, 99, 110))
        self.assertEqual(result.position, 0)
        self.assertEqual(result.fills[-1].quantity, 2)


class OrderProtectionTests(unittest.TestCase):
    state = OrderExecutionTests.state
    minute = OrderExecutionTests.minute

    def test_protection_update_resolves_fraction_once(self):
        state = self.minute(
            self.state(LimitOrder("buy", OrderSide.BUY, 100, 4)), (100, 101, 99, 100)
        )
        state.command(
            OrderCommand(
                120_000,
                OrderAction.PROTECT,
                "position",
                protection=OrderProtection(
                    90, (TakeProfitTier(105, fraction=0.5), TakeProfitTier(110, fraction=0.5))
                ),
            )
        )
        state = self.minute(state, (100, 106, 99, 105))
        self.assertEqual(state.position, 2)
        self.assertEqual(state.targets, [(110, 2)])

    def test_daily_entry_limit_survives_same_minute_stop(self):
        state = self.state(LimitOrder("buy", OrderSide.BUY, 100, 1, protection=OrderProtection(99)))
        state = self.minute(state, (100, 101, 98, 100), max_entries_per_day=1)
        state.command(
            OrderCommand(
                120_000, OrderAction.SUBMIT, "again", LimitOrder("again", OrderSide.BUY, 100, 1)
            )
        )
        state = self.minute(state, (100, 101, 99, 100), max_entries_per_day=1)
        self.assertEqual(state.position, 0)
        self.assertEqual(state.events[-1]["outcome"], "constraint_cancelled")

    def test_average_entry_relative_stop_updates_after_add(self):
        state = self.state(
            LimitOrder("first", OrderSide.BUY, 100, 1, protection=OrderProtection(stop_loss_pct=10))
        )
        state = self.minute(state, (100, 101, 99, 100))
        state.command(
            OrderCommand(
                120_000, OrderAction.SUBMIT, "add", LimitOrder("add", OrderSide.BUY, 110, 1)
            )
        )
        state = self.minute(state, (110, 111, 109, 110))
        self.assertEqual(state.average_entry, 105)
        self.assertEqual(state.stop_price, 94.5)


class ExpiredOrderUpdateTests(unittest.TestCase):
    def test_update_after_expiry_does_not_resurrect_order_across_gap(self):
        state = OrderExecutionState()
        order = LimitOrder("entry", OrderSide.BUY, 95, 1, expires_at_ms=120_000)
        state.command(OrderCommand(60_000, OrderAction.SUBMIT, "entry", order))
        updated = LimitOrder("entry", OrderSide.BUY, 99, 1, expires_at_ms=600_000)
        state.command(OrderCommand(180_000, OrderAction.UPDATE, "entry", updated))
        self.assertFalse(state.active)
        self.assertEqual(state.events[-1]["outcome"], "inactive_noop")
