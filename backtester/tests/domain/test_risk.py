import unittest

from domain.risk import (
    InstrumentSpec,
    ProtectionSetting,
    SizingPolicy,
    available_margin,
    size_entry,
)


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.instrument = InstrumentSpec(1, "USD", 1, 1, 1, 0.01)

    def size(self, mode, value, **overrides):
        args = dict(equity=10000, entry_price=100, direction=1, strategy_quantity=3, stop_price=95)
        args.update(overrides)
        return size_entry(SizingPolicy(mode, value), self.instrument, **args)

    def test_risk_and_exposure_are_distinct(self):
        self.assertEqual(self.size("risk", 100).quantity, 20)
        self.assertEqual(self.size("exposure", 100).quantity, 1)
        self.assertEqual(self.size("equity_risk", 1).planned_risk, 100)
        self.assertEqual(self.size("equity_exposure", 20).quantity, 20)

    def test_short_stop_and_invalid_stop(self):
        self.assertEqual(self.size("risk", 100, direction=-1, stop_price=105).quantity, 20)
        for stop in (None, 100, 101, float("nan")):
            self.assertEqual(self.size("risk", 100, stop_price=stop).reason, "invalid_stop")

    def test_rounding_never_increases_budget(self):
        result = self.size("risk", 103)
        self.assertEqual(result.quantity, 20)
        self.assertEqual(result.planned_risk, 100)
        self.assertEqual(self.size("exposure", 99).reason, "below_minimum_quantity")

    def test_equity_and_contract_value(self):
        self.assertEqual(self.size("equity_risk", 1, equity=5000).quantity, 10)
        spec = InstrumentSpec(1, "USD", 100, 0.1, 0.1, 0.01)
        decision = size_entry(
            SizingPolicy("risk", 100),
            spec,
            equity=10000,
            entry_price=100,
            direction=1,
            strategy_quantity=1,
            stop_price=95,
        )
        self.assertEqual(decision.quantity, 0.2)
        self.assertEqual(decision.planned_risk, 100)

    def test_margin_marks_current_exposure_and_reservations(self):
        self.assertEqual(
            available_margin(
                self.instrument,
                equity=1000,
                position=-20,
                price=110,
                leverage=10,
                reserved_margin=100,
            ),
            680,
        )

    def test_depleted_account_and_protective_levels(self):
        self.assertEqual(self.size("units", 1, equity=0).reason, "account_depleted")
        self.assertEqual(
            ProtectionSetting("ticks", 50).level(100, -1, self.instrument, stop=True), 100.5
        )
        self.assertEqual(
            ProtectionSetting("percent", 5).level(100, 1, self.instrument, stop=False), 105
        )

    def test_invalid_specs(self):
        with self.assertRaises(ValueError):
            InstrumentSpec(1, "USD", 0, 1, 1, 0.01)
        with self.assertRaises(ValueError):
            SizingPolicy("risk", None)
        with self.assertRaises(ValueError):
            SizingPolicy(leverage=0.5)
