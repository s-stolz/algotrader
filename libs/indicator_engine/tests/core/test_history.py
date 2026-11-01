import unittest

from indicator_engine import InputHistory
from indicator_engine.indicators.currency_strength import CurrencyStrength
from indicator_engine.indicators.sma import SMA


class InputHistoryTests(unittest.TestCase):
    def test_rolling_history_requests_available_predecessors(self) -> None:
        plan = SMA.spec.plan_history(start_ms=123456789, params={"window": 20})
        self.assertEqual(plan.start_ms, 123456789)
        self.assertEqual(plan.predecessor_bars, 19)

    def test_daily_history_expands_midday_request_to_midnight(self) -> None:
        midnight = 86_400_000 * 20000
        plan = CurrencyStrength.spec.plan_history(start_ms=midnight + 12 * 3_600_000, params={})
        self.assertEqual(plan.start_ms, midnight)
        self.assertEqual(plan.predecessor_bars, 1)

    def test_daily_history_still_needs_predecessor_at_midnight(self) -> None:
        plan = CurrencyStrength.spec.plan_history(start_ms=86_400_000, params={})
        self.assertEqual(plan.start_ms, 86_400_000)
        self.assertEqual(plan.predecessor_bars, 1)

    def test_single_bar_indicator_needs_no_predecessor(self) -> None:
        plan = SMA.spec.plan_history(start_ms=0, params={"window": 1})
        self.assertEqual(plan.predecessor_bars, 0)

    def test_invalid_history_requirements_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            InputHistory(predecessor_bars=-1)
        with self.assertRaises(ValueError):
            InputHistory().plan(start_ms=0, warmup_bars=0)
