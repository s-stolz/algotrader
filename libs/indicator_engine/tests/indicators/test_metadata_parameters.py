import unittest

from indicator_engine.indicators.bbands import BBANDS
from indicator_engine.indicators.macd import MACD
from indicator_engine.indicators.rsi import RSI
from indicator_engine.indicators.sma import SMA


class IndicatorMetadataParameterTests(unittest.TestCase):
    def test_source_parameter_options_are_exposed(self) -> None:
        expected = ["close", "open", "high", "low"]
        indicators = [SMA(), RSI(), BBANDS(), MACD()]

        for indicator in indicators:
            source = indicator.spec.parameters["source"]
            self.assertEqual(source.get("type"), "string")
            self.assertEqual(source.get("default"), "close")
            self.assertEqual(source.get("options"), expected)

    def test_bbands_ma_mode_options_are_exposed(self) -> None:
        ma_mode = BBANDS().spec.parameters["ma_mode"]
        self.assertEqual(ma_mode.get("type"), "string")
        self.assertEqual(ma_mode.get("default"), "SMA")
        self.assertEqual(ma_mode.get("options"), ["SMA", "EMA"])


if __name__ == "__main__":
    unittest.main()
