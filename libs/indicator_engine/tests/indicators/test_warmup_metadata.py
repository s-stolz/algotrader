import unittest

from indicator_engine.indicators.bbands import BBANDS
from indicator_engine.indicators.currency_strength import CurrencyStrength
from indicator_engine.indicators.macd import MACD
from indicator_engine.indicators.rsi import RSI
from indicator_engine.indicators.sma import SMA


class WarmupMetadataTests(unittest.TestCase):
    def test_sma_warmup_matches_window(self) -> None:
        self.assertEqual(SMA().spec.warmup({"window": 5}), 5)

    def test_rsi_warmup_is_length_plus_one(self) -> None:
        self.assertEqual(RSI().spec.warmup({"length": 14}), 15)

    def test_macd_warmup_is_slow_plus_signal(self) -> None:
        self.assertEqual(MACD().spec.warmup({"slow": 26, "signal": 9}), 35)

    def test_bbands_warmup_matches_length(self) -> None:
        self.assertEqual(BBANDS().spec.warmup({"length": 20}), 20)

    def test_currency_strength_warmup_is_two(self) -> None:
        self.assertEqual(CurrencyStrength().spec.warmup({}), 2)


if __name__ == "__main__":
    unittest.main()
