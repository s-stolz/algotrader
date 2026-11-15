import unittest
from typing import Any, Iterator

from domain.enums import OrderSide
from domain.orders import LimitOrder, OrderAction, OrderCommand, OrderProtection, TakeProfitTier
from domain.risk import InstrumentSpec, ProtectionMode, ProtectionSetting, SizingPolicy
from engines.order_events import EventOrderConfig, EventOrderState, execute_order_event
from execution.orders import OrderExecutionConfig, OrderExecutionState, execute_minute


class OrderRiskTests(unittest.TestCase):
    def runtimes(self, **overrides) -> Iterator[tuple[Any, Any, Any]]:
        fields: dict[str, Any] = dict(
            instrument=InstrumentSpec(1, "USD", 1, 1, 1, 0.01),
            sizing=SizingPolicy("risk", 100, 10),
            initial_capital=1000,
            stop_loss=ProtectionSetting("distance", 5),
        )
        fields.update(overrides)
        for config_type, state_type, execute in (
            (OrderExecutionConfig, OrderExecutionState, execute_minute),
            (EventOrderConfig, EventOrderState, execute_order_event),
        ):
            config: Any = config_type(**fields)
            yield config, state_type(config=config), execute

    def submit(self, state, identity, price=100):
        state.command(
            OrderCommand(
                60000, OrderAction.SUBMIT, identity, LimitOrder(identity, OrderSide.BUY, price, 1)
            )
        )

    def test_pending_quantity_and_reserved_margin(self):
        for config, state, execute in self.runtimes():
            self.submit(state, "one")
            self.assertEqual(state.active["one"].quantity, 20)
            self.assertEqual(state.reserved_margin(), 200)
            result = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 101, 99, 100), config=config
            )
            self.assertEqual(result.position, 20)
            self.assertEqual(result.stop_price, 95)

    def test_insufficient_margin_rejects_without_clamping(self):
        for config, state, execute in self.runtimes(sizing=SizingPolicy("risk", 100, 1)):
            self.submit(state, "one")
            self.assertFalse(state.active)
            self.assertEqual(state.events[-1]["outcome"], "insufficient_margin")

    def test_rejected_reversal_records_its_executed_close(self):
        for sizing, stop, rejection in (
            (SizingPolicy("units", 10, 1), ProtectionSetting("none"), "insufficient_margin"),
            (SizingPolicy("risk", 50, 10), ProtectionSetting("distance", 5), "invalid_stop"),
        ):
            for config, state, execute in self.runtimes(sizing=sizing, stop_loss=stop):
                with self.subTest(runtime=type(state).__name__, rejection=rejection):
                    state.position = 1
                    state.cash = -100
                    state.average_entry = 100
                    state.entry_timestamp_ms = 1
                    state.command(
                        OrderCommand(
                            60000,
                            OrderAction.SUBMIT,
                            "flip",
                            LimitOrder("flip", OrderSide.SELL, 100, 2),
                        )
                    )
                    self.assertEqual(state.active["flip"].quantity, 11)
                    result = execute(
                        state,
                        symbol="X",
                        timestamp_ms=60000,
                        prices=(200, 200, 200, 200),
                        config=config,
                    )
                    self.assertEqual(result.position, 0)
                    self.assertEqual(len(result.fills), 1)
                    self.assertEqual(result.fills[0].quantity, 1)
                    self.assertEqual(result.fills[0].side, OrderSide.SELL)
                    self.assertEqual(
                        result.events[-2],
                        dict(
                            timestamp_ms=60000,
                            order_id="flip",
                            outcome="filled",
                            quantity=1,
                            fill_price=200,
                        ),
                    )
                    self.assertEqual(result.events[-1]["outcome"], rejection)

    def test_stop_prevents_depletion(self):
        for config, state, execute in self.runtimes():
            self.submit(state, "one")
            result = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 100, 1, 50), config=config
            )
            self.assertFalse(result.depleted)
            self.assertEqual(result.fills[-1].price, 95)

    def test_intrabar_depletion_closes_position_and_cancels_orders(self):
        for config, state, execute in self.runtimes(
            sizing=SizingPolicy("units", 20, 10), stop_loss=ProtectionSetting("none")
        ):
            self.submit(state, "one")
            result = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 100, 40, 80), config=config
            )
            self.assertTrue(result.depleted)
            self.assertEqual(result.position, 0)
            self.assertFalse(result.active)
            self.assertEqual(result.fills[-1].price, 50)
            self.assertEqual(result.fills[-1].exit_reason.value, "account_depleted")

    def test_gap_preserves_negative_equity(self):
        for config, state, execute in self.runtimes(
            sizing=SizingPolicy("units", 20, 10), stop_loss=ProtectionSetting("none")
        ):
            self.submit(state, "one")
            result = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 100, 100, 100), config=config
            )
            result = execute(
                result, symbol="X", timestamp_ms=120000, prices=(40, 40, 40, 40), config=config
            )
            self.assertEqual(config.initial_capital + result.cash, -200)
            self.assertTrue(result.depleted)

    def test_addition_keeps_shared_stop_and_uses_its_distance(self):
        for config, state, execute in self.runtimes():
            self.submit(state, "one")
            state = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 101, 99, 100), config=config
            )
            self.submit(state, "two", price=105)
            self.assertEqual(state.active["two"].quantity, 10)
            state = execute(
                state, symbol="X", timestamp_ms=120000, prices=(105, 105, 104, 105), config=config
            )
            self.assertEqual(state.position, 30)
            self.assertEqual(state.stop_price, 95)

    def test_reduction_does_not_turn_into_a_reversal(self):
        for config, state, execute in self.runtimes():
            self.submit(state, "one")
            state = execute(
                state, symbol="X", timestamp_ms=60000, prices=(100, 100, 100, 100), config=config
            )
            state.command(
                OrderCommand(
                    120000,
                    OrderAction.SUBMIT,
                    "reduce",
                    LimitOrder("reduce", OrderSide.SELL, 100, 5),
                )
            )
            state = execute(
                state, symbol="X", timestamp_ms=120000, prices=(100, 100, 100, 100), config=config
            )
            self.assertEqual(state.position, 15)

    def test_reductions_respect_each_protection_source(self):
        modes: tuple[tuple[ProtectionMode, ProtectionMode], ...] = (
            ("distance", "distance"),
            ("none", "none"),
            ("strategy", "distance"),
            ("distance", "strategy"),
        )
        for stop_mode, target_mode in modes:
            for reduce_only in (True, False):
                for config, state, execute in self.runtimes(
                    sizing=SizingPolicy("units", 10, 10),
                    stop_loss=ProtectionSetting(stop_mode, 5 if stop_mode == "distance" else None),
                    take_profit=ProtectionSetting(
                        target_mode, 10 if target_mode == "distance" else None
                    ),
                ):
                    with self.subTest(
                        runtime=type(state).__name__,
                        stop=stop_mode,
                        target=target_mode,
                        reduce_only=reduce_only,
                    ):
                        self.submit(state, "entry")
                        state = execute(
                            state,
                            symbol="X",
                            timestamp_ms=60000,
                            prices=(100, 100, 100, 100),
                            config=config,
                        )
                        state.command(
                            OrderCommand(
                                120000,
                                OrderAction.SUBMIT,
                                "reduce",
                                LimitOrder(
                                    "reduce",
                                    OrderSide.SELL,
                                    100,
                                    5,
                                    reduce_only=reduce_only,
                                    protection=OrderProtection(
                                        stop_price=90,
                                        take_profits=(TakeProfitTier(120, fraction=1),),
                                    ),
                                ),
                            )
                        )
                        state = execute(
                            state,
                            symbol="X",
                            timestamp_ms=120000,
                            prices=(100, 100, 100, 100),
                            config=config,
                        )
                        self.assertEqual(state.position, 5)
                        self.assertEqual(
                            state.stop_price,
                            {"distance": 95, "none": None, "strategy": 90}[stop_mode],
                        )
                        self.assertEqual(
                            state.targets,
                            {"distance": [(110, 5)], "none": [], "strategy": [(120, 5)]}[
                                target_mode
                            ],
                        )
